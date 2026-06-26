import logging
from django.core.management.base import BaseCommand
from assessment.services.question_importer import (
    persist_validated_import,
    validate_and_prepare_import,
    write_status_file_to_path,
)

logger = logging.getLogger('django')


class Command(BaseCommand):
    """
    Import questions from an Excel template and insert them into the database.

    This command reads an Excel file containing questions, options, and metadata, 
    validates the data, and inserts it into the corresponding database tables. 
    It also generates a status file to indicate the success or failure of each row.

    How to Run:
    -----------
    1. Place the Excel template file in a known directory.
    2. Run the command using the following syntax:
       python manage.py import_questions --template_path <path_to_excel_file>

       Example:
       python manage.py import_questions --template_path "C:/path/to/questions_template.xlsx"
       python manage.py import_questions --template_path "C:/path/to/questions_template.xlsx" --create_questions

    3. After execution, check the same directory as the input file for a new file 
       with "_imported" appended to the filename. This file contains the import 
       status for each row.
     Excel Template Format:
    -----------------------
    The Excel file should have the following structure:
    - Metadata (first 7 rows):
        Row 1: Content
        Row 2: Level (G1L1, G1L2, etc.)
        Row 3: Subject (EN, COM, LS)
        Row 4: Sub-level (General, Phonics, etc.)
        Row 5: Question Type
        Row 6: Author Email
        Row 7: (Empty)

    - Questions (starting from row 8):
        Columns:
        - "Text Question" (required): The question text.
        - "Option1" to "Option5" (at least one required): The options for the question.
        - "Correct Option" (required): The correct option text matching one of the options.

    Notes:
    ------
    - If any required metadata or question data is missing, the row will be marked as failed.
    - The command uses transactions to ensure data integrity. If an error occurs, 
      no partial data will be saved.
    """
    help = 'Import questions from an Excel template and insert into corresponding tables.'

    def add_arguments(self, parser):
        parser.add_argument('--template_path', type=str, required=True, help='Path to the Excel template file')
        parser.add_argument(
            '--create_questions',
            action='store_true',
            help='Persist validated questions and write status file. Default is validation-only.',
        )

    def handle(self, *args, **options):
        template_path = options['template_path']
        should_create_questions = options.get('create_questions', False)

        try:
            import_result = validate_and_prepare_import(template_path, source_name=template_path)
            if not import_result.is_valid:
                write_status_file_to_path(template_path, import_result.meta_df, import_result.data_df)
                self.stdout.write(
                    self.style.ERROR(
                        f"Import failed. Metadata errors: {len(import_result.meta_errors)}, "
                        f"Row errors: {len(import_result.row_errors)}"
                    )
                )
                return

            if should_create_questions:
                persist_validated_import(import_result)
                write_status_file_to_path(template_path, import_result.meta_df, import_result.data_df)
                self.stdout.write(self.style.SUCCESS("Questions imported successfully."))
                logger.info(f"Questions imported successfully from {template_path}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Validation successful. No questions were created. "
                        "Use --create_questions to persist and write status file."
                    )
                )
                logger.info(f"Validation successful for {template_path} (dry run)")

        except Exception as e:
            logger.error(f"Failed to import questions: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Failed to import questions: {e}"))
