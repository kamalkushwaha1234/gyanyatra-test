import csv
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch
from assessment.models import Assessment, AssessmentResult, Answer, Organization

class Command(BaseCommand):
    help = 'Import assessment results from a CSV file'
    '''
    This command imports assessment results from a CSV file. The CSV file should contain the following columns:
    - Timestamp
    - Name
    - Question 
    - Multiple choice options (A, B, C, D)
    The command will create an AssessmentResult object for each row in the CSV file and associate the answers with it.
    The command also requires an email mapping CSV file to map names to email addresses.

    Usage:
        python manage.py create_assessment_result <assessment_id> <organization_id> <assessment_csv> <email_csv>
    Example:
        python manage.py create_assessment_result 12345 org_001 assessment_results.csv email_mapping.csv
    '''

    def add_arguments(self, parser):
        parser.add_argument('assessment_id', type=str, help="Assessment ID")
        parser.add_argument('organization_id', type=str, help="Organization ID")
        parser.add_argument('assessment_csv', type=str, help="Path to assessment CSV")
        parser.add_argument('email_csv', type=str, help="Path to email mapping CSV")
    def handle(self, *args, **options):
        assessment_id = options['assessment_id']
        file_path = options['assessment_csv']
        email_path = options['email_csv']
        organization_id = options['organization_id']
        
        try:
            assessment = Assessment.objects.get_with_prefetch(id=assessment_id)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fetching assessment: {e}"))
            raise CommandError(f"Error fetching assessment: {e}")

        except Assessment.DoesNotExist:
            raise CommandError(f"Assessment with ID {assessment_id} does not exist.")

        self.stdout.write(self.style.SUCCESS(f"Found Assessment: {assessment}"))

        self.import_assessment_results(file_path, assessment, email_path)

    def import_assessment_results(self, file_path, assessment, email_path,organization_id):
        question_list = list(assessment.questions.all().order_by('id'))

        try:
            organization = Organization.objects.get(id=organization_id)
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader)

                for col in reader:
                    # Check if the number of questions in the CSV matches the number of questions in the assessment
                    # skipped the two col (timestamp,name)
                    if len(col) - 2 != len(question_list):
                        self.stdout.write(self.style.ERROR(f"Invalid number of questions for {col[1]}"))
                        continue

                    email = self.get_email(col[1], email_path)
                    if not email:
                        self.stdout.write(self.style.ERROR(f"Email not found for {col[1]}"))
                        continue

                    start_time = datetime.strptime(col[0].strip().replace("“", "").replace("”", ""), "%m-%d-%Y %H:%M:%S")
                    end_time = start_time + timedelta(minutes=30)

                    #create assessment result  obj
                    assessment_result = AssessmentResult.create(
                        assessment=assessment,
                        name=col[1].strip(),
                        email=email,
                        grade="",
                        total_questions=len(col) - 2,
                        organization=organization,
                        attempted_questions=len(col) - 2,
                        start_time=start_time,
                        end_time=end_time,
                    )

                    answers = []

                    # check option and create answer 
                    for i, question in enumerate(question_list):
                        selected_char = col[i + 2].strip()[0]
                        options = list(question.options.all().order_by('id'))

                        selected_index = 0 if selected_char == 'A' else 1
                        selected_option = options[selected_index]
                        correct_index = 0 if options[0].id == question.correct_answer.id else 1

                        answers.append(
                            Answer(
                                question=question,
                                selected_option=selected_option,
                                is_correct=(selected_index == correct_index)
                            )
                        )

                    Answer.objects.bulk_create(answers)
                    assessment_result.answers.set(answers)
                    assessment_result.save()
                    self.stdout.write(self.style.SUCCESS(f"Created result for {assessment_result.name}"))

        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")
        except Exception as e:
            raise CommandError(f"Error during result import: {e}")

    def get_email(self, name, email_path):
        name = name.strip()
        first_name = name.split(" ")[0].lower()
        #skip anmol and hoor 
        if first_name in ['anmol', 'hoor']:
            return None

        try:
            with open(email_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                for col in reader:
                    if col and col[0].strip().lower().find(first_name) != -1:
                        if first_name == 'n':
                            return f"{name.split(' ')[1]}@enableindia.org"
                        if name == "Naveen Kumar M":
                            return "naveen.m@enableindia.org"
                        return col[1]
        except FileNotFoundError:
            raise CommandError(f"Email file not found at path: {email_path}")
        except Exception as e:
            raise CommandError(f"Error while retrieving email: {e}")

        return f"{first_name}@enableindia.org"

