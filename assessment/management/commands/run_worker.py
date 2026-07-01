import json
import time
import signal
import os
import logging
from django.core.management.base import BaseCommand
from assessment.models import AssessmentJob
from assessment.services.assessment_service import process_assessment

logger = logging.getLogger("django")


class Command(BaseCommand):
    help = "Continuously polls SQS and processes assessment jobs (equivalent to Azure WebJob)"

    def handle(self, *args, **options):
        queue_url = os.getenv("SQS_QUEUE_URL", "")
        region = os.getenv("AWS_REGION", "ap-south-1")

        if not queue_url:
            self.stderr.write("SQS_QUEUE_URL is not set. Exiting.")
            return

        try:
            import boto3
            client = boto3.client("sqs", region_name=region)
        except Exception as e:
            self.stderr.write(f"Failed to create SQS client: {e}")
            return

        self._running = True

        def shutdown(signum, frame):
            self.stdout.write("Shutdown signal received. Stopping worker...")
            self._running = False

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        self.stdout.write(f"Worker started. Polling SQS: {queue_url}")

        while self._running:
            try:
                response = client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,       # long polling — reduces empty-poll cost
                    VisibilityTimeout=300,    # 5 min — must exceed max job duration
                )

                for message in response.get("Messages", []):
                    receipt_handle = message["ReceiptHandle"]
                    job_id = None

                    try:
                        body = json.loads(message["Body"])
                        job_id = body.get("job_id")

                        if not job_id:
                            logger.error(f"Message missing job_id: {body}")
                            client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
                            continue

                        job = AssessmentJob.objects.get(job_id=job_id)
                        job.status = "processing"
                        job.save(update_fields=["status"])

                        result_id = process_assessment(job)

                        job.status = "completed"
                        job.result_id = result_id
                        job.save(update_fields=["status", "result_id"])

                        logger.info(f"Job {job_id} completed. result_id={result_id}")
                        client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

                    except AssessmentJob.DoesNotExist:
                        logger.error(f"Job {job_id} not found in DB — discarding message")
                        client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

                    except Exception as e:
                        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
                        try:
                            failed_job = AssessmentJob.objects.get(job_id=job_id)
                            failed_job.status = "failed"
                            failed_job.error = str(e)[:500]
                            failed_job.save(update_fields=["status", "error"])
                        except Exception:
                            pass
                        # Do NOT delete message — let SQS visibility timeout expire
                        # so it retries and eventually lands in the Dead Letter Queue

            except Exception as e:
                logger.error(f"SQS poll error: {e}", exc_info=True)
                time.sleep(5)

        self.stdout.write("Worker stopped.")
