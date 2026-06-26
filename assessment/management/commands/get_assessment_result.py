import csv
from django.core.management.base import BaseCommand, CommandError
from assessment.models import AssessmentResult
from datetime import datetime

class Command(BaseCommand):
    help = 'Export answers for an AssessmentResult to a CSV file.'
    """
        Management command to export answers from AssessmentResult(s) into a CSV file.

        Supported filters:
        - --assessment_result_id: ID of a specific AssessmentResult.
        - --assessment_id: ID of the Assessment to retrieve all related results.
        - --date: Date filter in YYYY-MM-DD format.
        - --timelamp: Direction of the date filter — either 'before' or 'after'.
        - output_csv_path: Required positional argument specifying the CSV file path to save the exported data.

        pass assessment_result_id when you want to export a specific result.
        pass assessment_id when you want to export all results related to a specific assessment.
        pass date in assessment_id when you want to filter results by date and also having option of before and after.

        CSV Output Format:
        Each exported row contains the following fields:
            - Category
            - Question
            - Selected Option
            - Correct Option

        For each AssessmentResult, the script:
        - Writes the student's name and date before listing their answers.
        - Adds an empty row after each student's answers for readability.

        example usage:
        python manage.py get_assessment_result --assessment_result_id 1 output.csv
        python manage.py get_assessment_result --assessment_id 1 --date 2023-10-01 --timelamp after output.csv
        python manage.py get_assessment_result --assessment_id 1 --date 2023-10-01 --timelamp before output.csv
        python manage.py get_assessment_result --assessment_id 1 output.csv
        python manage.py get_assessment_result --assessment_id 1 --date 2023-10-01 output.csv

        """


    def add_arguments(self, parser):
        parser.add_argument(
            '--assessment_result_id',
            type=int,
            help="ID of a specific AssessmentResult."
        )
        parser.add_argument(
            '--assessment_id',
            type=int,
            help="ID of the related Assessment."
        )
        parser.add_argument(
            '--date',
            type=str,
            help="Filter by date (YYYY-MM-DD) if exporting multiple results."
        )
        parser.add_argument(
            '--timelamp',
            type=str,
            choices=['before', 'after'],
            help="Specify date filter direction."
        )
        parser.add_argument(
            'output_csv_path',
            type=str,
            help="Output CSV file path."
        )

    def handle(self, *args, **options):
        result_id = options['assessment_result_id']
        assessment_id = options['assessment_id']
        date = options['date']
        timelamp = options['timelamp']
        file_path = options['output_csv_path']

        # Determine queryset or single instance
        assessment_results = None

        if result_id:
            try:
                assessment_results = AssessmentResult.objects.get_or_filter_answer_with_prefetch(
                    id=result_id, option="filter"
                )
            except AssessmentResult.DoesNotExist:
                raise CommandError(f"AssessmentResult with ID {result_id} does not exist.")
        elif assessment_id:
            filters = {"assessment__id": assessment_id}
            if date:
                try:
                    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
                    if timelamp == "after":
                        filters["date__date__gte"] = parsed_date
                    elif timelamp == "before":
                        filters["date__date__lte"] = parsed_date
                    else:
                        filters["date__date"] = parsed_date
                except ValueError:
                    raise CommandError("Invalid date format. Use YYYY-MM-DD.")
            assessment_results = AssessmentResult.objects.get_or_filter_answer_with_prefetch(
                option="filter", **filters
            )
            if not assessment_results.exists():
                raise CommandError("No AssessmentResults match the given filters.")
        else:
            raise CommandError("Provide either --assessment_result_id or --assessment_id.")

        self.export_answers(assessment_results, file_path)

    def export_answers(self, results, file_path):
        try:

            rows = [['Category', 'Question', 'Selected Option', 'Correct Option']]
            for result in results:
                answers = result.answers.all().order_by('question__category', 'question__id')
                writer.writerow([result.name, result.date.strftime("%Y-%m-%d")])
                for ans in answers:
                    category = ans.question.category if ans.question.category else "N/A"
                    rows.append([
                        category,
                        ans.question.question,
                        ans.selected_option.option,
                        ans.question.correct_answer.option if ans.question.correct_answer else "N/A"
                    ])
                rows.append([])  

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(rows)

            self.stdout.write(self.style.SUCCESS(f"Answers exported to {file_path}"))
        except Exception as e:
            raise CommandError(f"Error exporting answers: {e}")
