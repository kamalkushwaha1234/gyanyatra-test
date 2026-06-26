from django.core.management.base import BaseCommand
from assessment.models import Subject, Question, FillInTheBlank, AudioQuestion, Assessment


class Command(BaseCommand):
    help = """Corrects the subject field in Question, FillInTheBlank,
              AudioQuestion, and Assessment models based on old integer 
              values."""
    """
    Django management command to correct the `subject` field values in multiple models
    (Question, FillInTheBlank, AudioQuestion, and Assessment) where old subject values
    were stored as integers or strings like "1" or "2".

    This command performs the following operations:
    - Iterates over all instances of the specified models.
    - Maps old subject values:
        - "1" → Subject.ENGLISH
        - "2" → Subject.LIFE_SKILL
    - Updates and saves corrected subject values to the database.
    - Logs unmatched subject values for manual inspection.

    Arguments:
        No arguments are required.

    Usage:
        python manage.py restore_subject
    """

    def handle(self, *args, **options):
        """
        Entry point for the management command.
        Iterates over different model types and corrects their subject fields.
        """
        self.stdout.write("Starting subject correction...")

        models = [Question, FillInTheBlank, AudioQuestion, Assessment]
        for model in models:
            queryset = model.objects.all()
            self.correct_subject_field(queryset)
        
        self.stdout.write("Subject correction completed successfully.")

    def correct_subject_field(self, queryset):
        """
        Corrects the `subject` field in the given queryset.
        Assumes old values were strings like "1" for English and others for Life Skill.
        """
        for obj in queryset:
            if str(obj.subject) == "1":
                obj.subject = Subject.ENGLISH.value
            elif str(obj.subject) == "2":
                obj.subject = Subject.LIFE_SKILL.value
            else:
                self.stdout.write(f"subject {obj.subject} not match of question {obj.id}")
            obj.save()
