from django.core.management.base import BaseCommand
from assessment.models import Answer
from assessment.services.calculator import recalculate_answer


class Command(BaseCommand):
    help = "Recalculate answer scores for all types of assessment questions"
    """
    Django management command to recalculate scores for all submitted answers
    across different types of assessment questions.

    This command performs the following operations:
    - Fetches all `Answer` instances along with their related question types 
      using `select_related` for optimized database access.
    - Separately processes answers linked to:
        - Text-based questions (`question`)
        - Fill-in-the-blank questions (`fillup_question`)
        - Audio questions (`audio_question`)
    - For each answer type, it invokes the `recalculate_answer()` function 
      from the `assessment.services.calculator` module.

    Usage:
        python manage.py recalculate_answer_scores
    Arguments:
        No arguments are required.
    """

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting to recalculate answer scores...\n"))

        # Use select_related for FK performance optimization
        answers = Answer.objects.select_related('question', 'fillup_question', 'audio_question')

        try:
            text_answers = answers.filter(question__isnull=False)
            recalculate_answer(text_answers, send="Question")
            self.stdout.write(self.style.SUCCESS(f"Processed {text_answers.count()} text answers."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error processing text answers: {e}"))

        try:
            fill_answers = answers.filter(fillup_question__isnull=False)
            recalculate_answer(fill_answers, send="FillInTheBlank")
            self.stdout.write(self.style.SUCCESS(f"Processed {fill_answers.count()} fill-in-the-blank answers."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error processing fill-in-the-blank answers: {e}"))

        try:
            audio_answers = answers.filter(audio_question__isnull=False)
            recalculate_answer(audio_answers, send="AudioQuestion")
            self.stdout.write(self.style.SUCCESS(f"Processed {audio_answers.count()} audio answers."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error processing audio answers: {e}"))

        self.stdout.write(self.style.SUCCESS("\nFinished recalculating all answer scores."))
