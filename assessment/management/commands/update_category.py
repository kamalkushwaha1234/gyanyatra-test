from django.core.management.base import BaseCommand
from assessment.models import Category, Subject, Question

map_id_to_name = {
    "1": Category.EMPATHY.value,
    "2": Category.MANAGING_EMOTIONS.value,
    "3": Category.SELF_AWARENESS.value,
    "4": Category.SOCIAL_SKILL.value,
    "5": Category.MOTIVATING_ONESELF.value,
    "6": Category.DISMISSING.value,
    "7": Category.DISAPPROVING.value,
    "8": Category.LAISSEZ_FAIRE.value,
    "9": Category.EMOTION_COACHING.value,
    "10": Category.PMB.value,
    "11": Category.PMG.value,
    "12": Category.PVB.value,
    "13": Category.PVG.value,
    "15": Category.PSB.value,
    "16": Category.PSG.value,
}


class Command(BaseCommand):
    '''
    Command to map the category IDs to their value in Question.
    Usage: python manage.py update_category
    '''
    help = 'Remap category IDs to their corresponding values in Question.'

    def handle(self, *args, **options):
        self.stdout.write("Starting to update categories...")

        # Fetch all questions and update their categories based on the mapping
        questions = Question.objects.filter(subject=Subject.LIFE_SKILL.value)
        for question in questions:
            self.stdout.write(f"question Category {question.category}.")
            if question.category in map_id_to_name:
                question.category = map_id_to_name[question.category]
                question.save()
                self.stdout.write(f"Updated question {question.id} to category {question.category}.")
            else:
                self.stdout.write(f"No matching category found for question {question.id}.")

