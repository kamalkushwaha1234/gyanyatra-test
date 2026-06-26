from django.core.management.base import BaseCommand, CommandError
from assessment.models import AssessmentResult,Assessment
from assessment.services.calculator import ReEvaluation
from time import time


class Command(BaseCommand):
    '''
    This command recalculates scores for all AssessmentResults.
    It can be run with an optional assessment_id argument to target a specific assessment.
    python manage.py recalculate_scores --assessment_id <id>
    If no assessment_id is provided, it will process all assessments.
    Usage:
    python manage.py recalculate_scores
    python manage.py recalculate_scores --assessment_id 1
    '''
    help = 'Recalculate scores for all AssessmentResults.'
    def add_arguments(self, parser):
        parser.add_argument(
            '--assessment_id',
            type=int,
            help='ID of the assessment to recalculate scores for. If not provided, all assessments will be processed.'
        )

    def handle(self, *args, **options):
        assessment_id = options.get('assessment_id')
        start_time = time()
        self.stdout.write(self.style.NOTICE("Starting score recalculation..."))
        if assessment_id is not None:
            try:
                assessment = Assessment.objects.filter(id=assessment_id)
            except Assessment.DoesNotExist:
                raise CommandError(f'Assessment with ID {assessment_id} does not exist.')
        else:
            assessment= Assessment.objects.all()

        for assessment_instance in assessment:
            results = AssessmentResult.objects.filter(assessment=assessment_instance)
            if not results.exists():
                self.stdout.write(f"No results found for assessment {assessment_instance.id}.")
                continue
    
            self.stdout.write(f"Recalculating scores for assessment with ID {assessment_instance.id} and name {assessment_instance.name}")
            try:
                returned = ReEvaluation(results, assessment_instance.level)
                if returned is None:
                    self.stdout.write(f"No changes made for assessment {assessment_instance.id}.")
                else:
                    self.stdout.write(f"Scores recalculated successfully for assessment {assessment_instance.id}.")
            except Exception as e:
                self.stderr.write(f"Error recalculating scores for assessment {assessment_instance.id}: {str(e)}")

        elapsed_time = time() - start_time
        self.stdout.write(self.style.NOTICE(f"Score recalculation completed in {elapsed_time:.2f} seconds."))
