"""
Django management command to generate and distribute assessment summaries.

This module provides a Django management command that generates assessment summary reports
for specified users, filtered by subject and time period. The reports can be delivered via:
- Email (formatted HTML/text)
- CSV file download
- Both email and download

The command supports multiple report types (daily, weekly, monthly, custom) and allows
flexible filtering by user IDs and custom date ranges.

Usage examples:
    python manage.py send_weekly_subject_summary --user-ids 4,6 --report-type weekly
    python manage.py send_weekly_subject_summary --user-ids 4 --report-type custom --start-date 2026-01-01 --end-date 2026-01-31 --delivery both
    python manage.py send_weekly_subject_summary --organization-id 3 --report-type weekly --delivery email
    python manage.py send_weekly_subject_summary --user-ids 4 --report-type weekly --detail-report
"""

import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from assessment.models import Organization, Subject, User
from assessment.services import report as report_service


class Command(BaseCommand):
    """
    Generate assessment summary and deliver it via email and/or CSV download.
    
    This command generates comprehensive assessment summary reports for users,
    organized by subject and time period. It supports:
    - Multiple reporting periods (daily, weekly, monthly, or custom date range)
    - Flexible user selection via command-line arguments
    - Multiple delivery methods (email, CSV download, or both)
    - Organized output by subject with assessment counts and result counts
    """

    help = (
        "Send assessment summary email (daily/weekly/monthly/custom) for specific users. "
        "By default, user IDs are 4 and 6."
    )
    requires_system_checks = []

    # Default user IDs to process if none specified via command arguments
    DEFAULT_USER_IDS = [4, 6]
    
    # Predefined order for subject display in reports (ensures consistent ordering across all reports)
    SUBJECT_ORDER = [
        Subject.ENGLISH.value,
        Subject.COMPUTER.value,
        Subject.LIFE_SKILL.value,
    ]
    REPORT_SUBJECT_GROUPS = [
        ("english_computer", [Subject.ENGLISH.value, Subject.COMPUTER.value]),
        ("life_skill", [Subject.LIFE_SKILL.value]),
    ]
    
    # Delivery method constants for flexible report distribution
    DELIVERY_EMAIL = "email"          # Send summary via email
    DELIVERY_DOWNLOAD = "download"    # Generate CSV file for download
    DELIVERY_BOTH = "both"            # Both email and download

    def add_arguments(self, parser):
        """
        Register command-line arguments for the management command.
        
        Registers the following optional arguments:
        - user-ids: Comma-separated user IDs to process (default: 4,6)
        - report-type: Type of report (daily/weekly/monthly/custom, default: weekly)
        - start-date: Start date for custom reports in YYYY-MM-DD format
        - end-date: End date for custom reports in YYYY-MM-DD format
        - delivery: Report delivery method (email/download/both, default: email)
        - output-dir: Directory path for saving CSV reports (default: current working directory)
        """
        parser.add_argument(
            "--user-ids",
            type=str,
            default=None,
            help="Comma-separated user IDs to process. Default: 4,6 when --organization-id is not used",
        )
        parser.add_argument(
            "--report-type",
            type=str,
            choices=["daily", "weekly", "monthly", "custom"],
            default="weekly",
            help="Report duration type. Default: weekly",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for custom report in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="End date for custom report in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--delivery",
            type=str,
            choices=[self.DELIVERY_EMAIL, self.DELIVERY_DOWNLOAD, self.DELIVERY_BOTH],
            default=self.DELIVERY_EMAIL,
            help="Choose report delivery mode: email, download, or both. Default: email",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=os.getcwd(),
            help="Directory path to save generated report file(s).",
        )
        parser.add_argument(
            "--file-format",
            type=str,
            choices=["xlsx", "csv"],
            default="xlsx",
            help="Report file format. Default: xlsx",
        )
        parser.add_argument(
            "--exclude-assessment-ids",
            type=str,
            default="",
            help="Comma-separated assessment IDs to exclude from report.",
        )
        parser.add_argument(
            "--exclude-organization-ids",
            type=str,
            default="",
            help="Comma-separated organization IDs to exclude from report.",
        )
        parser.add_argument(
            "--organization-id",
            type=int,
            default=None,
            help=(
                "Optional organization ID. "
                "When set, includes only this organization's results and sends email to this organization."
            ),
        )
        parser.add_argument(
            "--detail-report",
            action="store_true",
            default=False,
            help=(
                "Generate detailed student-level report. "
                "By default this is false and summary report format is used."
            ),
        )

    def handle(self, *args, **options):
        """
        Main command entry point - orchestrates the entire report generation process.
        
        Workflow:
        1. Parse and validate command-line arguments (user IDs, report type, dates)
        2. Resolve the time window for the report based on report type
        3. Fetch users matching the specified user IDs
        4. For each user:
           - Build subject-based summary with assessment and result counts
           - Send email if delivery mode includes email
           - Generate CSV download if delivery mode includes download
        5. Output summary statistics (emails sent, reports downloaded)
        
        Error handling:
        - CommandError raised for invalid date formats or missing custom date parameters
        - Warnings logged for users without email addresses
        """
        user_ids_raw = options.get("user_ids")
        report_type = options["report_type"]
        start_date = options.get("start_date")
        end_date = options.get("end_date")
        delivery = options["delivery"]
        output_dir = options["output_dir"]
        file_format = options["file_format"]
        detail_report = options["detail_report"]
        exclude_assessment_ids = report_service._parse_user_ids(options.get("exclude_assessment_ids"))
        exclude_organization_ids = report_service._parse_user_ids(options.get("exclude_organization_ids"))
        target_organization_id = options.get("organization_id")
        target_organization = None
        if target_organization_id:
            if user_ids_raw:
                raise CommandError("--user-ids cannot be used with --organization-id.")
            target_organization = Organization.objects.filter(id=target_organization_id).first()
            if not target_organization:
                raise CommandError(f"Organization with id {target_organization_id} does not exist.")

        now = timezone.localtime(timezone.now())
        # Resolve the reporting time window based on report type and custom dates
        try:
            window_start, window_end, window_label = report_service._resolve_time_window(
                report_type=report_type,
                now=now,
                start_date=start_date,
                end_date=end_date,
            )
        except ValueError as exc:
            raise CommandError(str(exc))

        sent_count = 0
        downloaded_count = 0
        if target_organization_id:
            try:
                summary = report_service._build_user_summary(
                    user=None,
                    window_start=window_start,
                    window_end=window_end,
                    exclude_assessment_ids=exclude_assessment_ids,
                    exclude_organization_ids=exclude_organization_ids,
                    include_organization_id=target_organization_id,
                )

                report_file_paths = []
                for report_suffix, subject_codes in self.REPORT_SUBJECT_GROUPS:
                    report_result = report_service._download_report(
                        user=None,
                        summary=report_service._filter_summary_by_subject_codes(summary, subject_codes),
                        window_start=window_start,
                        window_end=window_end,
                        report_type=report_type,
                        window_label=window_label,
                        output_dir=output_dir,
                        file_format=file_format,
                        target_organization_id=target_organization_id,
                        detail_report=detail_report,
                        exclude_assessment_ids=exclude_assessment_ids,
                        exclude_organization_ids=exclude_organization_ids,
                        subject_codes=subject_codes,
                        report_suffix=report_suffix,
                    )
                    if isinstance(report_result, list):
                        report_file_paths.extend(report_result)
                    else:
                        report_file_paths.append(report_result)

                if delivery in [self.DELIVERY_EMAIL, self.DELIVERY_BOTH]:
                    recipient_email = target_organization.email
                    if not recipient_email:
                        self.stdout.write(
                            self.style.WARNING(f"Organization {target_organization.id} has no email. Email skipped.")
                        )
                    else:
                        report_service._send_email(
                            user=None,
                            summary=summary,
                            window_start=window_start,
                            window_end=window_end,
                            report_type=report_type,
                            window_label=window_label,
                            attachment_paths=report_file_paths,
                            recipient_email=recipient_email,
                            recipient_name=target_organization.name,
                        )
                        sent_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Summary email sent to organization {target_organization.id} ({recipient_email})."
                            )
                        )

                if delivery in [self.DELIVERY_DOWNLOAD, self.DELIVERY_BOTH]:
                    downloaded_count += len(report_file_paths)
                    for report_file_path in report_file_paths:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Report downloaded for organization {target_organization.id}: {report_file_path}"
                            )
                        )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to process organization {target_organization.id} "
                        f"({target_organization.email or 'no-email'}): {exc}"
                    )
                )
                return
        else:
            user_ids = report_service._parse_user_ids(user_ids_raw)
            if not user_ids:
                user_ids = self.DEFAULT_USER_IDS

            if not user_ids:
                self.stdout.write(self.style.WARNING("No valid user IDs found to process."))
                return

            users = User.objects.filter(id__in=user_ids).order_by("id")
            if not users.exists():
                self.stdout.write(self.style.WARNING("No matching users found."))
                return

            for user in users:
                try:
                    summary = report_service._build_user_summary(
                        user=user,
                        window_start=window_start,
                        window_end=window_end,
                        exclude_assessment_ids=exclude_assessment_ids,
                        exclude_organization_ids=exclude_organization_ids,
                        include_organization_id=None,
                    )
                    report_file_paths = []
                    for report_suffix, subject_codes in self.REPORT_SUBJECT_GROUPS:
                        report_result = report_service._download_report(
                            user=user,
                            summary=report_service._filter_summary_by_subject_codes(summary, subject_codes),
                            window_start=window_start,
                            window_end=window_end,
                            report_type=report_type,
                            window_label=window_label,
                            output_dir=output_dir,
                            file_format=file_format,
                            target_organization_id=None,
                            detail_report=detail_report,
                            exclude_assessment_ids=exclude_assessment_ids,
                            exclude_organization_ids=exclude_organization_ids,
                            subject_codes=subject_codes,
                            report_suffix=report_suffix,
                        )
                        if isinstance(report_result, list):
                            report_file_paths.extend(report_result)
                        else:
                            report_file_paths.append(report_result)

                    if delivery in [self.DELIVERY_EMAIL, self.DELIVERY_BOTH]:
                        if not user.email:
                            self.stdout.write(self.style.WARNING(f"User {user.id} has no email. Email skipped."))
                        else:
                            report_service._send_email(
                                user=user,
                                summary=summary,
                                window_start=window_start,
                                window_end=window_end,
                                report_type=report_type,
                                window_label=window_label,
                                attachment_paths=report_file_paths,
                                recipient_email=user.email,
                            )
                            sent_count += 1
                            self.stdout.write(self.style.SUCCESS(f"Summary email sent to user {user.id} ({user.email})."))

                    if delivery in [self.DELIVERY_DOWNLOAD, self.DELIVERY_BOTH]:
                        downloaded_count += len(report_file_paths)
                        for report_file_path in report_file_paths:
                            self.stdout.write(self.style.SUCCESS(f"Report downloaded for user {user.id}: {report_file_path}"))
                except Exception as exc:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Failed to process user {user.id} ({user.email or 'no-email'}): {exc}"
                        )
                    )
                    continue

        # Output final summary statistics
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Emails sent: {sent_count}. Reports downloaded: {downloaded_count}."
            )
        )
