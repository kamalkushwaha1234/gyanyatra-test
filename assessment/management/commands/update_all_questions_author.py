import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from assessment.models import Question, AudioQuestion, FillInTheBlank, User
# python manage.py update_all_questions_author --author_id 7 --old_ids 5 --sub_level General
# python manage.py update_all_questions_author --rollback

class Command(BaseCommand):
    help = 'Update author_id for multiple tables (Question, AudioQuestion, FillInTheBlank) while excluding given sub_level(s)'
    AUDIT_LOG_FILE = "author_update_audit.json"
    def add_arguments(self, parser):
        parser.add_argument(
            '--author_id',
            required=False,
            help='New author_id to set (must be an integer and exist in User table)'
        )
        parser.add_argument(
            '--old_ids',
            nargs='+',
            required=False,
            help='Old author_ids to update (space separated list, must be integers)'
        )
        parser.add_argument(
            '--sub_level',
            nargs='+',
            type=str,
            required=False,
            help='Sub-level(s) to exclude (space separated list, mandatory)'
        )
        parser.add_argument(
            '--rollback',
            action='store_true',
            help='Rollback last update operation from audit log'
        )

    def handle(self, *args, **options):
        if options.get("rollback"):
            self.rollback()
            return
        if not options.get('author_id'):
            raise CommandError("Missing required argument: --author_id")
        if not options.get('old_ids'):
            raise CommandError("Missing required argument: --old_ids")
        if not options.get('sub_level'):
            raise CommandError("Missing required argument: --sub_level")
        try:
            new_author_id = int(options.get('author_id'))
        except (ValueError, TypeError):
            raise CommandError("Invalid author_id. It must be an integer.")

        raw_old_ids = options.get('old_ids')
        old_ids = []
        try:
            for oid in raw_old_ids:
                old_ids.append(int(oid))
        except (ValueError, TypeError):
            raise CommandError("Invalid old_ids. All values must be integers.")

        exclude_sublevels = options.get('sub_level')

        if not User.objects.filter(id=new_author_id).exists():
            raise CommandError(f"author_id {new_author_id} does not exist in User table.")
        
        
        tables = [
            ("Question", Question),
            ("AudioQuestion", AudioQuestion),
            ("FillInTheBlank", FillInTheBlank),
        ]

        for table_name, model in tables:
            self.update_table(model, table_name, new_author_id, old_ids, exclude_sublevels)

    def update_table(self, model, table_name, new_author_id, old_ids, exclude_sublevels):
        """
        Generic function to update author_id in a given model
        """
        try:
            queryset = model.objects.filter(author_id__in=old_ids).exclude(sub_level__in=exclude_sublevels)
            if not queryset.exists():
                self.stdout.write(self.style.WARNING(f"[{table_name}] No records matched."))
                return
            
            # Save the exact mapping of id -> old_author_id
            id_to_old_author = dict(queryset.values_list('id', 'author_id'))
            updated_count = queryset.update(author_id=new_author_id)
            updated_ids = list(id_to_old_author.keys())

            self.stdout.write(self.style.SUCCESS(f"[{table_name}] Updated {updated_count} record(s)."))
            self.stdout.write(f"[{table_name}] Updated IDs: " + ", ".join(map(str, updated_ids)))
            self.write_audit_log(
                table_name, model.__name__, id_to_old_author, new_author_id, exclude_sublevels, updated_ids, updated_count
            )
        except Exception as e:
            raise CommandError(f"Error updating {table_name}: {str(e)}")
    def write_audit_log(self, table_name, model_name, id_to_old_author, new_author_id, exclude_sublevels, updated_ids, updated_count):
        audit_record = {
            "table": table_name,
            "model": model_name,
            "timestamp": datetime.now().isoformat(),
            "id_to_old_author": id_to_old_author,  # <-- exact mapping
            "new_author_id": new_author_id,
            "exclude_sublevels": exclude_sublevels,
            "updated_ids": updated_ids,
            "updated_count": updated_count,
        }

        if os.path.exists(self.AUDIT_LOG_FILE):
            with open(self.AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        logs.append(audit_record)

        with open(self.AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)

        self.stdout.write(self.style.NOTICE(f"[{table_name}] Audit record saved to {self.AUDIT_LOG_FILE}"))

    def rollback(self):
        """
        Rollback the last update operation from audit log
        """
        if not os.path.exists(self.AUDIT_LOG_FILE):
            self.stdout.write(self.style.ERROR("No audit log file found. Cannot rollback."))
            return

        with open(self.AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)

        if not logs:
            self.stdout.write(self.style.WARNING("Audit log is empty. Nothing to rollback."))
            return

        last_record = logs.pop()  # take the last update entry
        model_map = {
            "Question": Question,
            "AudioQuestion": AudioQuestion,
            "FillInTheBlank": FillInTheBlank,
        }

        model_name = last_record["model"]
        model = model_map.get(model_name)

        if not model:
            self.stdout.write(self.style.ERROR(f"Unknown model {model_name} in audit log. Cannot rollback."))
            return

        # Perform rollback
        try:
            id_to_old_author = last_record["id_to_old_author"]

            # Rollback each record individually
            rolled_back_count = 0
            for obj_id, old_author in id_to_old_author.items():
                rolled_back_count += model.objects.filter(id=obj_id).update(author_id=old_author)

            self.stdout.write(self.style.SUCCESS(
                f"Rolled back {rolled_back_count} record(s) in {last_record['table']} to their original author_ids"
            ))

        except Exception as e:
            raise CommandError(f"Error during rollback: {str(e)}")

        # Save the updated log (removing the rolled-back entry)
        with open(self.AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4)
