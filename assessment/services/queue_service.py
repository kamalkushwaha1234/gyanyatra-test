from django.conf import settings
import os
import json
import logging
from assessment.services.assessment_service import process_assessment
from assessment.models import AssessmentJob

logger = logging.getLogger(__name__)


class QueueService:
    def __init__(self):
        self.use_mock = os.getenv("USE_MOCK_QUEUE", "false").lower() == "true"
        self._client = None
        self._queue_url = os.getenv("SQS_QUEUE_URL", "")

        if not self.use_mock:
            try:
                import boto3
                self._client = boto3.client(
                    "sqs",
                    region_name=os.getenv("AWS_REGION", "ap-south-1"),
                )
            except Exception as e:
                logger.error(f"Failed to initialize SQS client: {e}")

    def send_message(self, job_id):
        if self.use_mock:
            job = None
            try:
                job = AssessmentJob.objects.get(job_id=job_id)
                result_id = process_assessment(job)
                job.status = "completed"
                job.result_id = result_id
                job.save()
                return True
            except Exception as e:
                if job:
                    job.status = "failed"
                    job.error = str(e)
                    job.save()
                return False
        else:
            try:
                self._client.send_message(
                    QueueUrl=self._queue_url,
                    MessageBody=json.dumps({"job_id": job_id}),
                )
                return True
            except Exception as e:
                logger.error(f"SQS delivery failed for job {job_id}: {e}")
                return False
