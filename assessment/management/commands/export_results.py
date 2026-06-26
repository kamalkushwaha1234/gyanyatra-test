import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from assessment.models import Assessment, AssessmentResult, Organization
from assessment.views.report import download_results


"""
Management command to export assessment results into CSV files.

Examples:
    python manage.py export_results --assessment_id 5
    python manage.py export_results --assessment_id 5 --orgs_id 3,7,12
    python manage.py export_results --assessment_id 5 --date 2025-01-10
"""


class Command(BaseCommand):
    """Export assessment results to CSV files (per organization or combined)."""

    help = "Export assessment results as CSV. Supports multiple org IDs and optional date filtering."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assessment_id",
            type=int,
            required=True,
            help="ID of the Assessment to export results for."
        )
        parser.add_argument(
            "--orgs_id",
            type=str,
            required=False,
            help="Comma-separated list of Organization IDs (optional)."
        )
        parser.add_argument(
            "--date",
            type=str,
            required=False,
            help="Filter by date (YYYY-MM-DD). Optional."
        )

    def handle(self, *args, **options):
        assessment_id = options.get("assessment_id")
        orgs_id = options.get("orgs_id")
        date_str = options.get("date")

        try:
            # Validate date
            valid_date = None
            if date_str:
                try:
                    valid_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    raise CommandError("Invalid date format. Use YYYY-MM-DD (Example: 2025-01-10).")

            # Validate assessment
            assessment = Assessment.objects.get(id=assessment_id)

            # Parse organization IDs (if provided)
            orgs = []
            if orgs_id:
                ids = [int(x) for x in orgs_id.split(",") if x.strip().isdigit()]
                orgs = list(Organization.objects.filter(id__in=ids))
                if not orgs:
                    raise CommandError("No valid organizations found for the provided IDs.")

            # If organizations provided → create separate CSV for each org
            if orgs:
                for org in orgs:
                    self.export_csv(
                        assessment=assessment,
                        org=org,
                        date=valid_date
                    )
            else:
                # No orgs → export all results in one CSV
                self.export_csv(
                    assessment=assessment,
                    org=None,
                    date=valid_date
                )

        except Exception as e:
            raise CommandError(f"Error exporting results: {e}")

    def export_csv(self, assessment, org=None, date=None):
        filters = {"assessment": assessment}

        if org:
            filters["organization"] = org

        if date:
            filters["date__gte"] = date

        results = AssessmentResult.objects.filter(**filters)

        if not results.exists():
            if org:
                raise CommandError(f"No results found for organization {org.id}.")
            raise CommandError("No results found for the given filters.")

        # Build filename
        filename = f"assessment_{assessment.id}"
        if org:
            filename += f"_org_{org.id}"
        if date:
            filename += f"_{date}"
        filename += ".csv"

        file_path = os.path.join(os.getcwd(), filename)

        # Save CSV
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            download_results(writer, results, response=None)

        self.stdout.write(self.style.SUCCESS(f"CSV saved successfully: {filename}"))
