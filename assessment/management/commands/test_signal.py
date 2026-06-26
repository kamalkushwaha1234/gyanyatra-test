import time
from django.core.management.base import BaseCommand
from assessment.models import Option  # adjust app name if needed

class Command(BaseCommand):
    help = "Measure how long it takes to update an Option record"

    def handle(self, *args, **kwargs):
        obj = Option.objects.first()
        if not obj:
            self.stdout.write(self.style.ERROR("No Option records found."))
            return

        start = time.time()
        obj.option = "Updated from management command"
        obj.save()
        end = time.time()

        elapsed = end - start
        self.stdout.write(self.style.SUCCESS(f"Time taken: {elapsed:.6f} seconds"))
