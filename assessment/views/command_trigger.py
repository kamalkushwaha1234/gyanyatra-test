import json
import logging
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from assessment.services.report import _normalize_comma_separated_ids

logger = logging.getLogger("django")

VALID_REPORT_TYPES = {"daily", "weekly", "monthly", "custom"}
VALID_DELIVERY_MODES = {"email", "download", "both"}
VALID_FILE_FORMATS = {"xlsx", "csv"}


@csrf_exempt
@require_POST
def run_summary_report_command(request):
    """
    Trigger send_weekly_subject_summary command over HTTP.

    Security:
    - Requires header `X-REPORT-TOKEN` matching settings.REPORT_TRIGGER_TOKEN.

    Body JSON (all optional):
    {
      "user_ids": "4,6",
      "organization_id": 3,
      "report_type": "weekly",
      "start_date": "2026-01-01",
      "end_date": "2026-01-31",
      "delivery": "email",
      "output_dir": "reports",
      "file_format": "xlsx",
      "exclude_assessment_ids": "1,2",
      "exclude_organization_ids": "3,4",
      "detail_report": false
    }
    """
    configured_token = getattr(settings, "REPORT_TRIGGER_TOKEN", "")
    request_token = request.headers.get("X-REPORT-TOKEN", "")
    if not configured_token:
        logger.error("REPORT_TRIGGER_TOKEN is not configured in settings")
        return JsonResponse(
            {"success": False, "message": "Server configuration error"}, 
            status=500
        )
    
    if request_token != configured_token:
        logger.warning(
            f"Unauthorized access attempt to run_summary_report_command "
            f"from IP: {request.META.get('REMOTE_ADDR', 'unknown')}"
        )
        return JsonResponse(
            {"success": False, "message": "Unauthorized"}, 
            status=401
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"success": False, "message": "Payload must be a JSON object"}, status=400)

    user_ids = payload.get("user_ids")
    organization_id = payload.get("organization_id")
    report_type = payload.get("report_type", "weekly")
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    delivery = payload.get("delivery", "email")
    output_dir = payload.get("output_dir")
    file_format = payload.get("file_format", "xlsx")
    exclude_assessment_ids = payload.get("exclude_assessment_ids", "")
    exclude_organization_ids = payload.get("exclude_organization_ids", "")
    detail_report = payload.get("detail_report", False)

    user_ids, error_message = _normalize_comma_separated_ids(user_ids, "user_ids")
    if error_message:
        return JsonResponse({"success": False, "message": error_message}, status=400)

    exclude_assessment_ids, error_message = _normalize_comma_separated_ids(
        exclude_assessment_ids,
        "exclude_assessment_ids",
    )
    if error_message:
        return JsonResponse({"success": False, "message": error_message}, status=400)

    exclude_organization_ids, error_message = _normalize_comma_separated_ids(
        exclude_organization_ids,
        "exclude_organization_ids",
    )
    if error_message:
        return JsonResponse({"success": False, "message": error_message}, status=400)

    if organization_id is not None:
        if isinstance(organization_id, bool):
            return JsonResponse({"success": False, "message": "Invalid organization_id"}, status=400)
        try:
            organization_id = int(organization_id)
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "message": "Invalid organization_id"}, status=400)
        if organization_id <= 0:
            return JsonResponse({"success": False, "message": "Invalid organization_id"}, status=400)

    if report_type not in VALID_REPORT_TYPES:
        return JsonResponse({"success": False, "message": "Invalid report_type"}, status=400)

    if delivery not in VALID_DELIVERY_MODES:
        return JsonResponse({"success": False, "message": "Invalid delivery mode"}, status=400)

    if file_format not in VALID_FILE_FORMATS:
        return JsonResponse({"success": False, "message": "Invalid file_format"}, status=400)

    if output_dir is not None and not isinstance(output_dir, str):
        return JsonResponse({"success": False, "message": "Invalid output_dir"}, status=400)

    for field_name, field_value in (("start_date", start_date), ("end_date", end_date)):
        if field_value is None:
            continue
        if not isinstance(field_value, str):
            return JsonResponse({"success": False, "message": f"Invalid {field_name}"}, status=400)
        try:
            datetime.strptime(field_value, "%Y-%m-%d")
        except ValueError:
            return JsonResponse(
                {"success": False, "message": f"Invalid {field_name}. Use YYYY-MM-DD"},
                status=400,
            )

    if report_type == "custom" and (not start_date or not end_date):
        return JsonResponse(
            {"success": False, "message": "start_date and end_date are required for custom report_type"},
            status=400,
        )

    if isinstance(detail_report, str):
        detail_report = detail_report.strip().lower() in {"1", "true", "yes"}
    elif not isinstance(detail_report, bool):
        return JsonResponse({"success": False, "message": "Invalid detail_report"}, status=400)

    command_kwargs = {
        "report_type": report_type,
        "delivery": delivery,
        "file_format": file_format,
        "detail_report": detail_report,
    }
    if user_ids:
        command_kwargs["user_ids"] = user_ids
    if organization_id:
        command_kwargs["organization_id"] = organization_id
    if start_date:
        command_kwargs["start_date"] = start_date
    if end_date:
        command_kwargs["end_date"] = end_date
    if output_dir:
        command_kwargs["output_dir"] = output_dir
    if exclude_assessment_ids:
        command_kwargs["exclude_assessment_ids"] = exclude_assessment_ids
    if exclude_organization_ids:
        command_kwargs["exclude_organization_ids"] = exclude_organization_ids

    try:
        logger.info("Executing send_weekly_subject_summary with params: %s", command_kwargs)
        call_command("send_weekly_subject_summary", **command_kwargs)
        logger.info("send_weekly_subject_summary executed successfully")
    except Exception as exc:
        logger.exception(
            "Failed to execute send_weekly_subject_summary command with params %s",
            command_kwargs,
        )
        return JsonResponse(
            {
                "success": False,
                "message": str(exc),
                "attempted_params": command_kwargs,
            },
            status=500,
        )

    return JsonResponse(
        {
            "success": True,
            "message": "Command executed successfully",
            "params": command_kwargs,
        },
        status=200,
    )
