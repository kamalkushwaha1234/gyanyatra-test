import os
from datetime import datetime, timedelta
from assessment.services.calculator import safe_division
from assessment.models import Assessment, AssessmentResult, Organization, Subject, User
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models.functions import TruncMonth
from django.db.models import Count, Q
from django.utils import timezone
from openpyxl import Workbook
import calendar
import logging
logger = logging.getLogger('django')

def _build_organization_report_rows(
        user,
        start_date=None,
        end_date=None,
        assessment_id=None,
        organization_id=None,
    ):
    result = []
    try:
        logger.info("Inside _build_organization_report_rows function")
        filters = {
            "assessment__author": user,
        }

        if start_date:
            filters["date__date__gte"] = start_date
        if end_date:
            filters["date__date__lte"] = end_date
        if assessment_id:
            filters["assessment_id"] = assessment_id
        if organization_id:
            filters["organization_id"] = organization_id

        qs = AssessmentResult.objects.filter(**filters)

        rows = (
            qs
            .annotate(month_date=TruncMonth("date"))
            .values(
                "month_date",
                "assessment_id",
                "assessment__name",
                "organization_id",
                "organization__name",
            )
            .annotate(assessments=Count("id"))
            .order_by("month_date", "organization__name", "assessment__name")
        )

        for row in rows:
            month_date = row["month_date"]
            if not month_date:
                continue

            result.append({
                "year": int(month_date.year),
                "month_num": int(month_date.month),
                "month": calendar.month_name[int(month_date.month)],
                "month_date": month_date.strftime("%Y-%m-%d"),
                "assessment_id": int(row["assessment_id"]),
                "assessment_name": row["assessment__name"],
                "organization_id": int(row["organization_id"]) if row["organization_id"] else None,
                "organization_name": row["organization__name"] or "-",
                "assessments": int(row["assessments"]),
            })
    except Exception as e:
        logger.error(
            "Error in _build_organization_report_rows: %s",
            e,
            exc_info=True,
        )

    return result


def _parse_user_ids(user_ids_raw):
    """
    Parse comma-separated user IDs and return unique sorted integer IDs.
    """
    ids = set()
    for value in (user_ids_raw or "").split(","):
        value = value.strip()
        if value.isdigit():
            ids.add(int(value))
    return sorted(ids)

def _normalize_comma_separated_ids(value, field_name):
    if value is None:
        return None, None
    if not isinstance(value, str):
        return None, f"{field_name} must be a comma-separated string"

    normalized_ids = [item.strip() for item in value.split(",") if item.strip()]
    if not all(item.isdigit() for item in normalized_ids):
        return None, f"Invalid {field_name} format"

    return ",".join(normalized_ids), None

def _resolve_time_window(report_type, now, start_date=None, end_date=None):
    """
    Resolve the reporting time window based on report type and custom dates.
    """
    if report_type == "daily":
        window_start = now - timedelta(days=1)
        return window_start, now, "Last 1 day"

    if report_type == "weekly":
        window_start = now - timedelta(days=7)
        return window_start, now, "Last 7 days"

    if report_type == "monthly":
        window_start = now - timedelta(days=30)
        return window_start, now, "Last 30 days"

    if not start_date or not end_date:
        raise ValueError("For custom report, both --start-date and --end-date are required.")

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.") from exc

    tz = timezone.get_current_timezone()
    window_start = timezone.make_aware(start_dt.replace(hour=0, minute=0, second=0, microsecond=0), tz)
    window_end = timezone.make_aware(end_dt.replace(hour=23, minute=59, second=59, microsecond=999999), tz)

    if window_start > window_end:
        raise ValueError("--start-date cannot be greater than --end-date.")

    label = f"Custom range {start_date} to {end_date}"
    return window_start, window_end, label


def _filter_summary_by_subject_codes(summary, subject_codes):
    allowed = set(subject_codes or [])
    return [block for block in summary if block.get("subject_code") in allowed]


def _build_user_summary(
    user,
    window_start,
    window_end,
    exclude_assessment_ids=None,
    exclude_organization_ids=None,
    include_organization_id=None,
):
    """
    Build per-subject assessment summary for a specific user.
    """
    exclude_assessment_ids = exclude_assessment_ids or []
    exclude_organization_ids = exclude_organization_ids or []

    subject_map = {
        Subject.ENGLISH.value: Subject.ENGLISH.label,
        Subject.COMPUTER.value: Subject.COMPUTER.label,
        Subject.LIFE_SKILL.value: Subject.LIFE_SKILL.label,
    }

    subject_order = [
        Subject.ENGLISH.value,
        Subject.COMPUTER.value,
        Subject.LIFE_SKILL.value,
    ]

    summary = []
    for subject_code in subject_order:
        subject_label = subject_map.get(subject_code, subject_code)
        assessments = (
            Assessment.objects.filter(subject=subject_code)
            .order_by("id")
        )

        if user is not None:
            assessments = assessments.filter(author_id=user.id)
        if exclude_assessment_ids:
            assessments = assessments.exclude(id__in=exclude_assessment_ids)

        if not assessments:
            continue

        assessment_items = []
        for assessment in assessments:
            result_qs = AssessmentResult.objects.filter(
                assessment_id=assessment.id,
                date__gte=window_start,
                date__lte=window_end,
            )
            if include_organization_id:
                result_qs = result_qs.filter(organization_id=include_organization_id)
            if exclude_organization_ids:
                result_qs = result_qs.exclude(organization_id__in=exclude_organization_ids)

            if not result_qs:
                continue

            org_breakdown = []
            if include_organization_id:
                org = Organization.objects.filter(id=include_organization_id).first()
                if org:
                    org_breakdown.append(
                        {
                            "organization_id": org.id,
                            "organization_name": org.name,
                            "result_count": result_qs.count(),
                        }
                    )
            else:
                org_rows = (
                    result_qs.values("organization_id", "organization__name")
                    .annotate(result_count=Count("id"))
                    .order_by("organization__name")
                )
                for row in org_rows:
                    if row["organization_id"] in exclude_organization_ids:
                        continue
                    org_breakdown.append(
                        {
                            "organization_id": row["organization_id"],
                            "organization_name": row["organization__name"] or "Unassigned",
                            "result_count": row["result_count"],
                        }
                    )

            assessment_items.append(
                {
                    "assessment_id": assessment.id,
                    "assessment_name": assessment.name,
                    "result_count": result_qs.count(),
                    "organization_results": org_breakdown,
                }
            )

        if len(assessment_items)>0:
            summary.append(
                {
                    "subject_code": subject_code,
                    "subject_label": subject_label,
                    "assessment_count": len(assessment_items),
                    "assessments": assessment_items,
                }
            )

    return summary


def _send_email(
    user,
    summary,
    window_start,
    window_end,
    report_type,
    window_label,
    attachment_paths=None,
    recipient_email=None,
    recipient_name=None,
):
    resolved_recipient_email = recipient_email or (user.email if user else "")
    from_email = getattr(settings, "EMAIL_HOST_USER", "")

    if not resolved_recipient_email:
        raise ValueError("Recipient email is required to send summary email.")
    if not from_email:
        raise ValueError("EMAIL_HOST_USER is not configured.")

    try:
        subject = f"{report_type.title()} Assessment Results Summary"

        if recipient_name:
            greeting_name = recipient_name
        elif user:
            greeting_name = (
                f"{user.first_name} {user.last_name}"
                if user.last_name else user.first_name
            )
        else:
            greeting_name = "Team"

        table_rows = ""

        for subject_block in summary:
            total_assessment_result = sum(
                item["result_count"] for item in subject_block["assessments"]
            )

            subject_name = f"{subject_block['subject_label']} ({subject_block['subject_code']})"

            table_rows += f"""
            <tr>
                <td style="padding:8px;border:1px solid #ddd;">{subject_name}</td>
                <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                    {subject_block['assessment_count']}
                </td>
                <td style="padding:8px;border:1px solid #ddd;text-align:center;">
                    {total_assessment_result}
                </td>
            </tr>
            """

        html_body = f"""
        <p>Dear {greeting_name},</p>

        <p>Please find below the <b>{report_type} assessment summary</b> for the selected reporting period.</p>

        <p>
        <b>Reporting Time:</b> from {window_start:%Y-%m-%d %H:%M:%S} to {window_end:%Y-%m-%d %H:%M:%S}
        </p>

        <table style="border-collapse:collapse;width:100%;font-family:Arial;">
            <thead>
                <tr style="background-color:#f2f2f2;">
                    <th style="padding:10px;border:1px solid #ddd;text-align:left;">
                        Subject
                    </th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:center;">
                        Assessments Conducted
                    </th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:center;">
                        Total Submissions
                    </th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <br>

        <p>Thanks,<br>
        Prishni Team</p>
        """

        body_text = "Please view this email in HTML format."

        email_message = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_email,
            to=[resolved_recipient_email],
            bcc=getattr(settings, "REPORT_EMAIL_BCC", []),
            cc=getattr(settings, "REPORT_EMAIL_CC", []),
        )

        email_message.attach_alternative(html_body, "text/html")

        for attachment_path in (attachment_paths or []):
            if attachment_path and os.path.exists(attachment_path):
                try:
                    email_message.attach_file(attachment_path)
                except Exception as exc:
                    logger.warning("Failed to attach file %s: %s", attachment_path, exc)

        email_message.send()
        logger.info("Email sent successfully to %s", resolved_recipient_email)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", resolved_recipient_email, exc, exc_info=True)
        raise


def _download_report(
    user,
    summary,
    window_start,
    window_end,
    report_type,
    window_label,
    output_dir,
    file_format,
    target_organization_id=None,
    detail_report=False,
    exclude_assessment_ids=None,
    exclude_organization_ids=None,
    subject_codes=None,
    report_suffix=None,
):
    os.makedirs(output_dir, exist_ok=True)

    timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d_%H%M%S")

    def build_file_path(suffix_override=None):
        suffix_value = suffix_override if suffix_override is not None else report_suffix
        suffix = f"_{suffix_value}" if suffix_value else ""
        if user is not None:
            org_suffix = f"_org_{target_organization_id}" if target_organization_id else ""
            file_name = f"assessment_summary_user_{user.id}{org_suffix}{suffix}_{report_type}_{timestamp}.{file_format}"
        elif target_organization_id:
            file_name = f"assessment_summary_org_{target_organization_id}{suffix}_{report_type}_{timestamp}.{file_format}"
        else:
            file_name = f"assessment_summary{suffix}_{report_type}_{timestamp}.{file_format}"
        return os.path.join(output_dir, file_name)

    file_path = build_file_path()

    exclude_assessment_ids = exclude_assessment_ids or []
    exclude_organization_ids = exclude_organization_ids or []

    def write_report(file_path, headers, rows):
        try:
            if file_format == "xlsx":
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Assessment Summary"
                sheet.append(headers)
                for row in rows:
                    sheet.append(row)
                workbook.save(file_path)
            else:
                import csv
                with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(headers)
                    writer.writerows(rows)
            
            logger.info(f"Report successfully written to {file_path}")
        
        except IOError as exc:
            logger.error(f"Failed to write report to {file_path}: {exc}", exc_info=True)
            raise

    if detail_report:
        headers = [
            "Assessment_name",
            "Assessment_id",
            "Student name",
            "Student email",
            "Subject",
            "Organisation",
            "Date",
            "Total Marks",
        ]
        detail_qs = AssessmentResult.objects.select_related("assessment", "organization").filter(
            date__gte=window_start,
            date__lte=window_end,
        )
        if user is not None:
            detail_qs = detail_qs.filter(assessment__author_id=user.id)
        if subject_codes:
            detail_qs = detail_qs.filter(assessment__subject__in=subject_codes)
        if target_organization_id:
            detail_qs = detail_qs.filter(organization_id=target_organization_id)
        if exclude_assessment_ids:
            detail_qs = detail_qs.exclude(assessment_id__in=exclude_assessment_ids)
        if exclude_organization_ids:
            detail_qs = detail_qs.exclude(organization_id__in=exclude_organization_ids)

        level_filters = None
        if subject_codes and Subject.LIFE_SKILL in subject_codes:
            level_filters = ["LS1EIQ1", "LS1MO1", "LS1FS1"]
            detail_qs = detail_qs.filter(assessment__level__in=level_filters)

        detail_qs = detail_qs.order_by("assessment_id", "date")

        if not level_filters:
            detail_results = list(detail_qs)
            rows = []
            for result in detail_results:
                rows.append(
                    [
                        result.assessment.name,
                        result.assessment_id,
                        result.name,
                        result.email,
                        Subject.getlabel(result.assessment.subject),
                        result.organization.name if result.organization_id else "Unassigned",
                        result.date.strftime("%Y-%m-%d %H:%M:%S"),
                        result.new_score.get("total_score", 0),
                    ]
                )

        if level_filters:
            extra_paths = []
            for level in level_filters:
                level_rows = []
                if level == "LS1EIQ1":
                    detail_results_eq = detail_qs.filter(assessment__level="LS1EIQ1")
                    if not detail_results_eq:
                        continue
                    headers = [
                        "Assessment_name",
                        "Assessment_id",
                        "Student name",
                        "Student email",
                        "Subject",
                        "Organisation",
                        "Date",
                        "Self awareness",
                        "Managing emotions",
                        "Motivating oneself",
                        "Empathy",
                        "Social Skill",
                    ]
                    for result in detail_results_eq:
                        level_rows.append(
                            [
                                result.assessment.name,
                                result.assessment_id,
                                result.name,
                                result.email,
                                Subject.getlabel(result.assessment.subject),
                                result.organization.name if result.organization_id else "Unassigned",
                                result.date.strftime("%Y-%m-%d %H:%M:%S"),
                                result.new_score.get("SA", 0),
                                result.new_score.get("ME", 0),
                                result.new_score.get("MO", 0),
                                result.new_score.get("EP", 0),
                                result.new_score.get("SS", 0),
                            ]
                        )
                if level == "LS1MO1":
                    detail_results_mo = detail_qs.filter(assessment__level="LS1MO1")
                    if not detail_results_mo:
                        continue
                    headers = [
                        "Assessment_name",
                        "Assessment_id",
                        "Student name",
                        "Student email",
                        "Subject",
                        "Organisation",
                        "Date",
                        "PmB",
                        "PmG",
                        "PvB",
                        "PvG",
                        "HoB",
                        "PsB",
                        "PsG",
                        "Total B",
                        "Total G",
                        "Total G-B",
                    ]
                    for result in detail_results_mo:
                        pmb = result.new_score.get("PmB", 0)
                        pmg = result.new_score.get("PmG", 0)
                        pvb = result.new_score.get("PvB", 0)
                        pvg = result.new_score.get("PvG", 0)
                        psb = result.new_score.get("PsB", 0)
                        psg = result.new_score.get("PsG", 0)
                        total_b = pmb + pvb + psb
                        total_g = pmg + pvg + psg
                        level_rows.append(
                            [
                                result.assessment.name,
                                result.assessment_id,
                                result.name,
                                result.email,
                                Subject.getlabel(result.assessment.subject),
                                result.organization.name if result.organization_id else "Unassigned",
                                result.date.strftime("%Y-%m-%d %H:%M:%S"),
                                pmb,
                                pmg,
                                pvb,
                                pvg,
                                pvb + pmb,
                                psb,
                                psg,
                                total_b,
                                total_g,
                                total_g - total_b,
                            ]
                        )
                if level == "LS1FS1":
                    detail_results_fs = detail_qs.filter(assessment__level="LS1FS1")
                    if not detail_results_fs:
                        continue
                    headers = [
                        "Assessment_name",
                        "Assessment_id",
                        "Student name",
                        "Student email",
                        "Subject",
                        "Organisation",
                        "Date",
                        "Dismissing",
                        "Disapproving",
                        "Laissez Faire",
                        "Emotion Coaching",
                    ]
                    for result in detail_results_fs:
                        assessment_answer=result.answers.all()
                        total_question_type = {
                            item['question__category']: item['count']
                            for item in assessment_answer.values('question__category').annotate(count=Count('id'))
                        }
                        level_rows.append(
                            [
                                result.assessment.name,
                                result.assessment_id,
                                result.name,
                                result.email,
                                Subject.getlabel(result.assessment.subject),
                                result.organization.name if result.organization_id else "Unassigned",
                                result.date.strftime("%Y-%m-%d %H:%M:%S"),
                                safe_division(result.new_score.get('DM', 0), total_question_type.get('DM', 0)),
                                safe_division(result.new_score.get('DAP', 0), total_question_type.get('DAP', 0)),
                                safe_division(result.new_score.get('LF', 0), total_question_type.get('LF', 0)),
                                safe_division(result.new_score.get('EC', 0), total_question_type.get('EC', 0)),
                            ]
                        )
                if level_rows:
                    level_file_path = build_file_path(suffix_override=f"{report_suffix}_{level}")
                    write_report(level_file_path, headers, level_rows)
                    extra_paths.append(level_file_path)
            return extra_paths
        write_report(file_path, headers, rows)
    else:
        headers = [
            "Assessment_name",
            "Assessment_id",
            "Subject",
            "Organisation",
            "Start",
            "End",
            "Result_count",
        ]
        rows = []
        for subject_block in summary:
            if not subject_block["assessments"]:
                rows.append(
                    [
                        "",
                        "",
                        subject_block["subject_label"],
                        "",
                        window_start.strftime("%Y-%m-%d %H:%M:%S"),
                        window_end.strftime("%Y-%m-%d %H:%M:%S"),
                        0,
                    ]
                )
                continue

            for item in subject_block["assessments"]:
                if item["organization_results"]:
                    for org_item in item["organization_results"]:
                        rows.append(
                            [
                                item["assessment_name"],
                                item["assessment_id"],
                                subject_block["subject_label"],
                                org_item["organization_name"],
                                window_start.strftime("%Y-%m-%d %H:%M:%S"),
                                window_end.strftime("%Y-%m-%d %H:%M:%S"),
                                org_item["result_count"],
                            ]
                        )
                else:
                    rows.append(
                        [
                            item["assessment_name"],
                            item["assessment_id"],
                            subject_block["subject_label"],
                            "Unassigned",
                            window_start.strftime("%Y-%m-%d %H:%M:%S"),
                            window_end.strftime("%Y-%m-%d %H:%M:%S"),
                            item["result_count"],
                        ]
                    )

    write_report(file_path, headers, rows)

    return file_path
