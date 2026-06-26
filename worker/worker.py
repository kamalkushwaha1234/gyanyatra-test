"""
Azure Queue worker for asynchronous assessment processing.

Design goals:
1. Keep message handling simple and observable with structured logs.
2. Ensure each job update is transactional to avoid partial DB state.
3. Let Azure Queue drive retries by *not* deleting failed messages.

Message contract:
- Expected body: {"job_id": "<uuid-or-id>"}.
- Messages missing/invalid payload are treated as poison and deleted.
- Valid messages are deleted only after successful processing/completion.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
import traceback
import json
from time import perf_counter
from dataclasses import dataclass
from typing import Optional

_UNSET = object()  # Sentinel for optional parameters that distinguishes between "not provided" and "explicitly None"
from azure.storage.queue import QueueClient, QueueMessage
from azure.core.exceptions import AzureError


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assessmentPrishni.settings")

import django
django.setup()

from django.db import close_old_connections, transaction
from assessment.models import AssessmentJob, StatusChoices
from assessment.services.assessment_service import process_assessment
from assessmentPrishni.settings import AZURE_QUEUE_CONNECTION, QUEUE_NAME




# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

log_file = os.path.join(os.path.dirname(__file__), "worker.log")
handlers = [
    logging.StreamHandler(),
    logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    ),
]

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers,
)
logger = logging.getLogger("assessment_worker")
logger.info("=" * 80)
logger.info("Assessment Worker Started")
logger.info("=" * 80)


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

@dataclass
class WorkerConfig:
    """
    Runtime tuning for queue polling and retry behavior.

    Notes:
    - `max_retries` applies to top-level loop failures (queue/network/runtime).
    - `max_consecutive_errors` throttles hot error loops with a cool-down pause.
    - `visibility_timeout` is documented for operational context (Azure-side lock
      duration per dequeue) even if not explicitly passed in every call.
    """
    azure_queue_connection: str
    queue_name: str 
    messages_per_page: int = 5
    queue_poll_interval: float = 2.0
    max_consecutive_errors: int = 3
    consecutive_error_pause: float = 30.0
    max_retries: int = 5
    retry_backoff: float = 5.0
    visibility_timeout: int = 300  # 5 minutes
    max_dequeue_count: int = 5  # Max times to dequeue a message before treating it as poison


def _status_from_choices(status_key: str) -> str:
    """Return canonical status value from model `StatusChoices`."""
    for value, _label in StatusChoices:
        if value == status_key:
            return value
    raise ValueError(f"Status '{status_key}' is not defined in StatusChoices")


STATUS_IN_PROGRESS = _status_from_choices("in_progress")
STATUS_COMPLETED = _status_from_choices("completed")
STATUS_FAILED = _status_from_choices("failed")


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_config() -> WorkerConfig:
    """
    Load and validate worker configuration.

    Exits the process on missing mandatory settings because the worker cannot
    perform useful work without a queue connection.
    """
    azure_queue_connection = AZURE_QUEUE_CONNECTION
    queue_name = QUEUE_NAME

    if not azure_queue_connection:
        logger.critical("STARTUP ERROR: Missing AZURE_QUEUE_CONNECTION environment variable")
        logger.critical("Please set this environment variable in Azure App Service")
        sys.exit(1)
    if not queue_name:
        logger.critical("STARTUP ERROR: Missing QUEUE_NAME environment variable")
        logger.critical("Please set this environment variable in Azure App Service")
        sys.exit(1)
    
    logger.info("All configuration variables loaded successfully")
    return WorkerConfig(azure_queue_connection=azure_queue_connection, queue_name=queue_name)


config = load_config()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log_duration(label: str, start_time: float, level=logging.INFO, **context) -> float:
    """Log the duration of an operation."""
    duration = perf_counter() - start_time
    if context:
        context_str = ", ".join(f"{key}={value}" for key, value in context.items())
        logger.log(level, "%s took %.3f seconds (%s)", label, duration, context_str)
    else:
        logger.log(level, "%s took %.3f seconds", label, duration)
    return duration


def parse_message_data(message: QueueMessage) -> dict:
    """
    Parse and validate raw queue message content into a dict payload.

    Raises:
        ValueError: If payload is invalid JSON or not an object-like mapping.
    """
    try:
        data = message.content
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in message: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to parse message data: {e}") from e


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def update_job_status(
    job: AssessmentJob,
    status: str,
    result_id: object = _UNSET,
    error: object = _UNSET,
) -> None:
    """
    Update job status in database.

    Pass `result_id` or `error` to write those fields; omit them to leave
    the existing DB values untouched. Pass `None` explicitly to clear a field.

    Raises:
        Exception: If database update fails
    """
    try:
        job.status = status
        update_fields = ["status"]
        if result_id is not _UNSET:
            job.result_id = result_id
            update_fields.append("result_id")
        if error is not _UNSET:
            job.error = error
            update_fields.append("error")
        job.save(update_fields=update_fields)
        logger.info("Job %s status updated to '%s'", job.job_id, status)
    except Exception as exc:
        logger.error(
            "Unexpected error updating job %s: %s: %s",
            job.job_id,
            type(exc).__name__,
            exc,
        )
        logger.debug(traceback.format_exc())
        raise


def get_job_by_id(job_id: str) -> Optional[AssessmentJob]:
    """
    Fetch job by ID.

    Returns `None` when job is missing or a DB read error happens. The caller
    decides whether to retry or drop the corresponding message.
    """
    try:
        return AssessmentJob.objects.filter(job_id=job_id).first()
    except Exception as e:
        logger.error("Error fetching job %s: %s", job_id, e)
        return None


# ============================================================================
# QUEUE CLIENT MANAGEMENT
# ============================================================================

def create_queue_client(config: WorkerConfig) -> QueueClient:
    """
    Create and validate Azure Queue client.
    
    Args:
        config: Worker configuration
        
    Returns:
        QueueClient instance
        
    Raises:
        AzureError: If connection fails
    """
    try:
        logger.info("Connecting to Azure Queue...")
        queue = QueueClient.from_connection_string(
            conn_str=config.azure_queue_connection,
            queue_name=config.queue_name,
        )
        logger.info("Connected to Azure Queue successfully")
        return queue
    except AzureError as exc:
        logger.critical(
            "Failed to connect to Azure Queue: %s: %s",
            type(exc).__name__,
            exc,
        )
        logger.debug(traceback.format_exc())
        raise


# ============================================================================
# MESSAGE PROCESSING
# ============================================================================

@dataclass
class ProcessingResult:
    """Result of processing a single message."""
    success: bool
    job_id: Optional[str] = None
    result_id: Optional[str] = None
    error_message: Optional[str] = None
    should_delete_message: bool = False


def process_message(message: QueueMessage, config: WorkerConfig) -> ProcessingResult:
    """
    Process a single queue message.

    Returns ProcessingResult; caller is responsible for deleting the message
    from the queue when should_delete_message is True.
    """
    job_id = None

    # Poison-message guard: reject on fifth dequeue or beyond.
    if message.dequeue_count >= config.max_dequeue_count:
        logger.warning(
            "Message dequeued %d times (max %d) - treating as poison, deleting.",
            message.dequeue_count,
            config.max_dequeue_count,
        )
        try:
            job_id = parse_message_data(message).get("job_id")
        except ValueError:
            pass

        if job_id:
            try:
                with transaction.atomic():
                    poison_job = AssessmentJob.objects.filter(job_id=job_id).first()
                    if poison_job and poison_job.status != STATUS_COMPLETED:
                        update_job_status(
                            poison_job,
                            STATUS_FAILED,
                            error=f"Exceeded max processing attempts ({config.max_dequeue_count})",
                        )
            except Exception as exc:
                logger.error("Could not mark poison job %s as failed: %s", job_id, exc)

        return ProcessingResult(
            success=False,
            job_id=job_id,
            error_message="Exceeded max processing attempts",
            should_delete_message=True,
        )

    try:
        try:
            data = parse_message_data(message)
        except ValueError as e:
            logger.warning("Failed to parse message: %s - deleting from queue", e)
            return ProcessingResult(
                success=False,
                error_message=str(e),
                should_delete_message=True,
            )

        job_id = data.get("job_id")
        if not job_id:
            logger.warning("Message has no job_id: %s - deleting from queue", message.content)
            return ProcessingResult(
                success=False,
                error_message="Missing job_id",
                should_delete_message=True,
            )

        job = get_job_by_id(job_id)
        if not job:
            logger.warning(
                "Job %s is missing or currently locked by another worker - will retry",
                job_id,
            )
            return ProcessingResult(
                success=False,
                job_id=job_id,
                error_message="Job not found or locked",
                should_delete_message=False,
            )

        # One message = one DB transaction boundary for job state transitions.
        with transaction.atomic():
            if job.status == STATUS_COMPLETED:
                logger.info("Job %s already completed, deleting from queue", job_id)
                return ProcessingResult(
                    success=True,
                    job_id=job_id,
                    should_delete_message=True,
                )

            update_job_status(job, STATUS_IN_PROGRESS)

            logger.info("Starting assessment processing for job %s...", job_id)
            process_assessment_start = perf_counter()
            result_id = process_assessment(job)
            log_duration("process_assessment", process_assessment_start, job_id=job_id)

            job.refresh_from_db()

            update_job_status(job, STATUS_COMPLETED, result_id=result_id, error=None)

        logger.info("Job %s completed successfully. Result ID: %s", job_id, result_id)
        return ProcessingResult(
            success=True,
            job_id=job_id,
            result_id=result_id,
            should_delete_message=True,
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Job %s processing failed: %s", job_id, error_msg)
        logger.debug(traceback.format_exc())

        # Separate transaction so failure metadata is committed even when the
        # processing transaction rolls back.
        if job_id:
            try:
                with transaction.atomic():
                    failed_job = AssessmentJob.objects.filter(job_id=job_id).first()
                    if failed_job and failed_job.status != STATUS_COMPLETED:
                        update_job_status(failed_job, STATUS_FAILED, error=error_msg)
            except Exception as status_exc:
                logger.error(
                    "Could not mark job %s as failed: %s: %s",
                    job_id,
                    type(status_exc).__name__,
                    status_exc,
                )
                logger.debug(traceback.format_exc())

        # Keep message in queue — Azure visibility timeout will re-deliver it.
        logger.warning("Message NOT deleted from queue - will be retried by Azure Queue")
        return ProcessingResult(
            success=False,
            job_id=job_id,
            error_message=error_msg,
            should_delete_message=False,
        )


# ============================================================================
# QUEUE PROCESSING LOOP
# ============================================================================

@dataclass
class IterationStats:
    """Statistics for a queue processing iteration."""
    message_count: int = 0
    successful_count: int = 0
    failed_count: int = 0


def process_queue():
    """
    Main long-running queue processing loop.

    Control flow:
    - Poll queue in batches.
    - Process each message independently.
    - Delete only messages that are safe to acknowledge.
    - Back off on repeated failures to protect DB/queue and reduce log noise.
    """
    retry_count = 0
    consecutive_errors = 0
    
    # Create queue client
    try:
        queue = create_queue_client(config)
    except AzureError:
        sys.exit(1)
    
    logger.info("Starting main processing loop...")
    
    while True:
        loop_start = perf_counter()
        stats = IterationStats()
        
        try:
            # Keep Django DB connections healthy in a long-lived worker process.
            close_old_connections()
            
            logger.debug("Fetching messages from queue...")
            messages = queue.receive_messages(messages_per_page=config.messages_per_page,visibility_timeout=config.visibility_timeout)
            
            for message in messages:
                stats.message_count += 1
                logger.debug("Processing message %d...", stats.message_count)
                
                result = process_message(message, config)
                
                if result.success:
                    stats.successful_count += 1
                else:
                    stats.failed_count += 1
                
                # Delete only when the message has reached a terminal handled state.
                if result.should_delete_message:
                    try:
                        queue.delete_message(message)
                        logger.debug("Message deleted from queue")
                    except AzureError as e:
                        logger.warning("Failed to delete message: %s", e)
            
            # Batch-level accounting for operational stability.
            retry_count = 0
            
            if stats.message_count == 0:
                logger.debug("No messages received from queue")
                consecutive_errors = 0
            else:
                logger.info(
                    "Processed %d message(s) - Successful: %d, Failed: %d",
                    stats.message_count,
                    stats.successful_count,
                    stats.failed_count,
                )
                
                if stats.failed_count == 0:
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    
                    if consecutive_errors >= config.max_consecutive_errors:
                        logger.critical(
                            "%d consecutive errors detected. Pausing for %.1f seconds...",
                            consecutive_errors,
                            config.consecutive_error_pause,
                        )
                        time.sleep(config.consecutive_error_pause)
                        consecutive_errors = 0
            
            logger.debug(
                "Waiting %.1f seconds before next queue check...",
                config.queue_poll_interval,
            )
            log_duration(
                "process_queue iteration",
                loop_start,
                message_count=stats.message_count,
                successful_count=stats.successful_count,
                failed_count=stats.failed_count,
            )
            time.sleep(config.queue_poll_interval)
        
        except AzureError as exc:
            logger.error("Azure Queue error: %s: %s", type(exc).__name__, exc)
            logger.debug(traceback.format_exc())
            retry_count += 1
            consecutive_errors += 1
            
            if retry_count >= config.max_retries:
                logger.critical(
                    "Max retries (%d) reached. Exiting...",
                    config.max_retries,
                )
                sys.exit(1)
            
            logger.info(
                "Waiting %.1f seconds before retry (attempt %d/%d)...",
                config.retry_backoff,
                retry_count,
                config.max_retries,
            )
            log_duration(
                "process_queue iteration",
                loop_start,
                level=logging.ERROR,
            )
            time.sleep(config.retry_backoff)
        
        except Exception as exc:
            logger.error("Unexpected error in queue processing loop: %s: %s", type(exc).__name__, exc)
            logger.debug(traceback.format_exc())
            retry_count += 1
            consecutive_errors += 1
            
            if retry_count >= config.max_retries:
                logger.critical(
                    "Max retries (%d) reached after unexpected error. Exiting...",
                    config.max_retries,
                )
                sys.exit(1)
            
            logger.info(
                "Waiting %.1f seconds before retry (attempt %d/%d)...",
                config.retry_backoff,
                retry_count,
                config.max_retries,
            )
            log_duration(
                "process_queue iteration",
                loop_start,
                level=logging.ERROR,
            )
            time.sleep(config.retry_backoff)
        
        finally:
            close_old_connections()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        logger.info("Starting worker initialization...")
        process_queue()
    except Exception as exc:
        logger.critical("Critical startup error: %s: %s", type(exc).__name__, exc)
        logger.debug(traceback.format_exc())
        sys.exit(1)
