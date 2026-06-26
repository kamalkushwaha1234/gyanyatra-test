import csv
from django.core.management.base import BaseCommand, CommandError
from assessment.models import Assessment
from django.db.models import Prefetch

class Command(BaseCommand):
    help = 'Export correct answers for an Assessment to a CSV file'
    '''
    This command exports the correct answers for an Assessment  to a CSV file. 
    Usage:
        python manage.py get_assessment_question <assessment_id> <assessment_csv> <level>
    Example:
        python manage.py get_assessment_question 12345 assessment_results.csv basic
    This command will create a CSV file with the correct answers for the specified assessment.
    The CSV file will contain the following columns:
    - Category
    - Question
    - Correct Option
    The command also allows for an advanced export which includes all options and the correct option.
    Usage:
        python manage.py get_assessment_question <assessment_id> <assessment_csv> advance
    Example:
        python manage.py get_assessment_question 12345 assessment_results.csv advance
    This command will create a CSV file with the correct answers and all options for the specified assessment.
    The CSV file will contain the following columns:
    - Category
    - Question
    - Multiple choice options (A, B, C, D)
    - Correct Option
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'assessment_id',
            type=int,
            help="Specify the ID of the Assessment."
        )
        parser.add_argument(
            'assessment_csv',
            type=str,
            help="Path to the CSV file where correct answers will be saved."
        )
        parser.add_argument(
            'level',
            type=str,
            help="Specify export type: 'basic' or 'advance'"
        )

    def handle(self, *args, **options):
        assessment_id = options['assessment_id']
        file_path = options['assessment_csv']
        option = options['level']

        try:
            assessment = Assessment.objects.get_with_prefetch(id=assessment_id)
        except Assessment.DoesNotExist:
            raise CommandError(f"Assessment with ID {assessment_id} does not exist.")

        self.stdout.write(self.style.SUCCESS(f"Found Assessment: {assessment}"))
        if option == "basic":
            # Export category, question, and correct option
            self.export_correct_answers(assessment, file_path)
        elif option == "advance":
            # Export category, question, all options, and correct option
            self.export_question_detail(assessment, file_path)
        else:
            raise CommandError(f" Please provide the level basic or advance.")

    def export_correct_answers(self, assessment, file_path):
        try:

            rows =[['Category', 'Question', 'Correct Option']]
            for question in assessment.questions.all().order_by('category', 'id'):
                category = question.category if question.category else "N/A"
                correct_option = question.correct_answer.option if question.correct_answer else "N/A"
                rows.append([category, question.question, correct_option])

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(rows)

            self.stdout.write(self.style.SUCCESS("Correct answers exported successfully."))

        except Exception as e:
            raise CommandError(f"Error while writing to CSV: {e}")
    
    def export_question_detail(self, assessment, file_path):
        try:
            max_options = 0

            rows=[]
            for question in assessment.questions.all().order_by('category', 'id'):
                if question.options.count() > max_options:
                    max_options = question.options.count()

                options = question.options.all()
                category = question.category if question.category else "N/A"
                row = [category, question.question]
                row.extend([opt.option for opt in options])

                row.append(question.correct_answer if question.correct_answer else "N/A")
                rows.append(row)
                
            # Build the header dynamically
            header = ['Category', 'Question']
            for i in range(1, max_options + 1):
                header.append(f'Option {i}')
            header.append('Correct Option')

            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(header)
                writer.writerows(rows)
            
            self.stdout.write(self.style.SUCCESS("Question Details exported successfully."))
        except Exception as e:
            raise CommandError(f"Error exporting question detail: {e}")

