from django.conf import settings
import os
from assessment.services.assessment_service import process_assessment
from assessment.models import AssessmentJob
import json
import logging

logger = logging.getLogger(__name__)


class QueueService:
    def __init__(self):
        self.use_mock = os.getenv("USE_MOCK_QUEUE", "false").lower() == "true"
        self._client = None
        
        if not self.use_mock:
            try:
                from azure.storage.queue import QueueClient
                self._client = QueueClient.from_connection_string(
                    conn_str=settings.AZURE_QUEUE_CONNECTION,
                    queue_name=settings.QUEUE_NAME
                )
            except Exception as e:
                logger.error(f"Failed to initialize Azure Queue Client: {e}")

    def send_message(self, job_id):
        if self.use_mock:
            try:
                job = AssessmentJob.objects.get(job_id=job_id)
                result_id = process_assessment(job)
                job.status = "completed"
                job.result_id = result_id
                job.save()
                return True
            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.save()
                return False
        else:
            try:
                # Production: Azure Queue
                self._client.send_message(json.dumps({"job_id": job_id}))
                return True
            except Exception as e:
                logger.error(f"Azure Queue delivery failed for job {job_id}: {e}")
                return False
