from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime
import logging
from assessment.grading import GRADING
import random
from django.db.models import Count,Prefetch
from assessment.models import (
    ASSESSMENT_LEVELS,
    SUB_LEVELS,
    Assessment,
    AudioQuestion,
    Disability,
    Organization,
    Question,
    Option,
    Answer,
    AssessmentResult,
    Subject,
    FillInTheBlank,
    MAP_SUBLEVELS_TO_SUBJECT,
    SUBJECTS_HAVING_SUBLEVELS,
    Category,
    AssessmentJob,
)
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib import messages
from assessmentPrishni import settings
from assessmentPrishni.settings import SEND_EMAIL, AZURE_QUEUE_CONNECTION
from django.core.cache import cache
import json
from django.db import transaction
from assessment.services.curd_question import _parse_sublevel_distribution, _safe_int, _select_for_type, _select_random_by_content
from assessment.services.user_context_service import get_client_ip
try:
    from azure.storage.queue import QueueClient
    AZURE_QUEUE_AVAILABLE = True
except Exception:
    QueueClient = None
    AZURE_QUEUE_AVAILABLE = False
import uuid
from assessment.services.queue_service import QueueService


logger = logging.getLogger("django")


def sendMail(
    request, email, name, score, grade, course, organization, description, start_time, end_time
):
    logger.info(f"Sending email to {email}")
    subject = f"Assessment Result - {course}"
    message = render_to_string(
        "partials/email.html",
        {
            "name": name,
            "score": score,
            "grade": grade,
            "course": course,
            "organization": organization.name if organization else "",
            "description": description,
            "start_time": start_time.strftime("%B %d, %Y %I:%M:%S %p"),
            "end_time": end_time.strftime("%B %d, %Y %I:%M:%S %p"),
        },
    )
    email_from = ""
    recipient_list = [email]
    try:
        send_mail(
            subject=subject,
            message="",
            from_email=email_from,
            recipient_list=recipient_list,
            html_message=message,
        )
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        # messages.error(
        #     request,
        #     "There was an error while sending the email. But your Assessment Result was saved.",
        # )
    return

def generate_assessment(request):
    try:
        logger.info(f"User {request.user} is trying to generate an assessment generate_assessment ")
        if request.user.is_anonymous or (
            not request.user.is_superuser and not request.user.is_creator
        ):
            return render(
                request,
                "home.html",
                {
                    "error": "Welcome to the Gyanyatra portal, please login to continue, or contact your administrator for access."
                },
            )

        # GET renders the form plus availability metadata by subject/level/sub-level.
        if request.method == "GET":
            total_questions = {}
            # Fetching all subjects and calculating total questions for each subject
            try:
                model_map = {
                    "Questions": Question,
                    "Audios": AudioQuestion,
                    "Fillups": FillInTheBlank,
                }
                for subject in Subject:
                    sub=subject.label
                    total_questions[sub] = {}
                    for key, model_cls in model_map.items():
                        total_questions[sub][key] = list(
                            model_cls.objects.filter(author=request.user, subject=subject.value)
                            .values('level', 'sub_level')
                            .annotate(count=Count('id', distinct=True))
                        )
            except Exception as e:
                logger.error(f"Error while calculating total questions: {e}")
                total_questions = {}
            return render(
                request,
                "generate-assessment.html",
                {
                    "subjects": Subject.getSubjectDict(),
                    "total_questions": total_questions,
                    "ASSESSMENT_LEVELS": ASSESSMENT_LEVELS,
                    "SUB_LEVELS": SUB_LEVELS,
                    "MAP_SUBLEVELS_TO_SUBJECT":json.dumps(MAP_SUBLEVELS_TO_SUBJECT),
                    "SUBJECTS_HAVING_SUBLEVELS": SUBJECTS_HAVING_SUBLEVELS,
                },
            )
        try:
            # Life Skill assessments do not use sub-level on this form flow.
            excluded_sub_levels = [Subject.LIFE_SKILL.value]
            name = (request.POST.get("name") or "").strip()
            level = (request.POST.get("level") or "").strip()
            subject_value = (request.POST.get("subject") or "").strip()
            sub_level = (request.POST.get("sub_level") or "").strip()
            text_question_check = request.POST.get("text_question") == "on"
            audio_question_check = request.POST.get("audio_question") == "on"
            fill_in_the_blank_check = request.POST.get("fill_in_the_blank") == "on"

            text_question_count = _safe_int(request.POST.get("text_question_count"))
            audio_question_count = _safe_int(request.POST.get("audio_question_count"))
            fill_in_the_blank_count = _safe_int(request.POST.get("fill_in_the_blank_count"))
            show_correct_answer = str(
                request.POST.get("show_correct_answer_to_the_student", "False")
            ).strip().lower() == "true"
            shuffle_question = str(
                request.POST.get("shuffle_question_and_answer", "False")
            ).strip().lower() == "true"

            # Basic required metadata checks before any selection.
            if not name or not level or not subject_value:
                messages.error(request, "Please provide name, level and subject.")
                return redirect("generate_assessment")

            if not any([text_question_check, audio_question_check, fill_in_the_blank_check]):
                messages.error(request, "Please select at least one question type.")
                return redirect("generate_assessment")

            # Subject label is used to decide whether sub-level distribution is required.
            subject_label = ""
            try:
                subject_label = Subject(subject_value).label
            except Exception:
                subject_label = ""
            has_sublevels = subject_label in SUBJECTS_HAVING_SUBLEVELS

            # Clear plain sub-level when subject either forbids it (LS) or uses distribution mode.
            if subject_value in excluded_sub_levels or has_sublevels:
                sub_level = ""

            # Parse client-sent per-sublevel counts (text/audio/fillup).
            sublevel_distribution = _parse_sublevel_distribution(
                request.POST.get("sublevel_distribution_json", "")
            )
            selected_sublevels = set()

            # Shared base filters applied to all question types.
            filter_dict = {
                "level": level,
                "subject": subject_value,
            }
            if sub_level and not has_sublevels:
                filter_dict["sub_level"] = sub_level

            allowed_sublevels = {code for code, _ in MAP_SUBLEVELS_TO_SUBJECT.get(subject_value, [])}

            # Query only selected types; selection happens in DB via _select_random_by_content.
            type_config = {
                "text": {
                    "enabled": text_question_check,
                    "model": Question,
                    "count": text_question_count,
                    "distribution_key": "text",
                    "label": "text questions",
                    "m2m_field": "questions",
                },
                "audio": {
                    "enabled": audio_question_check,
                    "model": AudioQuestion,
                    "count": audio_question_count,
                    "distribution_key": "audio",
                    "label": "audio questions",
                    "m2m_field": "audio_questions",
                },
                "fillup": {
                    "enabled": fill_in_the_blank_check,
                    "model": FillInTheBlank,
                    "count": fill_in_the_blank_count,
                    "distribution_key": "fillup",
                    "label": "fill-in-the-blank questions",
                    "m2m_field": "fillup_questions",
                },
            }

            selected_by_field = {}
            total_selected = 0
            for cfg in type_config.values():
                if not cfg["enabled"]:
                    continue
                selected_items, error_msg, used_subs = _select_for_type(
                    queryset=cfg["model"].objects.filter(author=request.user),
                    requested_count=cfg["count"],
                    distribution_key=cfg["distribution_key"],
                    label=cfg["label"],
                    has_sublevels=has_sublevels,
                    sublevel_distribution=sublevel_distribution,
                    allowed_sublevels=allowed_sublevels,
                    filter_dict=filter_dict,
                )
                if selected_items is None:
                    messages.error(request, error_msg)
                    return redirect("generate_assessment")
                selected_sublevels.update(used_subs)
                selected_by_field[cfg["m2m_field"]] = selected_items
                total_selected += len(selected_items)

            if total_selected <= 0:
                messages.error(request, "Please select at least one question.")
                return redirect("generate_assessment")

            # Persist assessment and M2M links atomically to avoid partial saves.
            with transaction.atomic():
                assessment = Assessment.objects.create(
                    name=name,
                    level=level,
                    author=request.user,
                    subject=subject_value,
                    show_correct_answer=show_correct_answer,
                    shuffle_question=shuffle_question,
                    sub_level=sub_level,
                )

                for m2m_field, selected_items in selected_by_field.items():
                    if selected_items:
                        getattr(assessment, m2m_field).add(*selected_items)

                if has_sublevels:
                    if len(selected_sublevels) == 1:
                        assessment.sub_level = next(iter(selected_sublevels))
                    elif len(selected_sublevels) > 1:
                        assessment.sub_level = "Mixed"
                    else:
                        assessment.sub_level = ""
                    assessment.save(update_fields=["sub_level"])
            return redirect("assessment_list")
        except Exception as e:
                logger.error(f"Error while generating assessment: {e}")
                messages.error(request, "There was an error while generating the assessment.")
                return redirect("generate_assessment")
    except Exception as e:
        logger.error(f"Error in generate_assessment view: {e}")
        return render(
            request,
            "home.html",
            {
                "error": "There was an error while generating the assessment. Please try again later."
            },
        )

def take_assessment(request, id, slug):
    client_ip = get_client_ip(request)
    logger.info(f"User {request.user} with IP {client_ip} is trying to take the assessment {id}")
    try:
        assessment=Assessment.objects.get_with_prefetch(id=id)
    except Assessment.DoesNotExist:
        logger.error(f"Assessment with id {id} does not exist.")
        return render(
            request,
            "home.html",
            {
                "error": "The assessment you are trying to access is not available.",
            },
        )

    url = request.get_full_path()
    if url.split("/")[-2] != slug or not assessment.active:
        return render(
            request,
            "home.html",
            {
                "error": "The assessment you are trying to access is not available.",
            },
        )

    all_questions = {}
    if assessment.subject == Subject.LIFE_SKILL.value:
        assessment_questions= assessment.questions.all().order_by("pk")
        assessment_audio_questions = assessment.audio_questions.all().order_by("pk")
        assessment_fillup = assessment.fillup_questions.all().order_by("pk")

    else:
        assessment_questions= assessment.questions.all()
        assessment_audio_questions = assessment.audio_questions.all()
        assessment_fillup = assessment.fillup_questions.all()
    
    # Shuffle questions and options 
    if assessment.shuffle_question:
        assessment_questions= list(assessment_questions)
        random.shuffle(assessment_questions)
        
    for q in assessment_questions:
            q.shuffled_options = list(q.options.all())
            if assessment.shuffle_question :
                random.shuffle(q.shuffled_options)
    
    for question in assessment_questions:
        content = question.content.content
        all_questions.setdefault(content, {}).setdefault("question", []).append(question)
    
    for question in assessment_audio_questions:
        content = question.content.content
        all_questions.setdefault(content, {}).setdefault("audio_question", []).append(question)
    
    for question in assessment_fillup:
        content = question.content.content
        question.sentence_parts = question.sentence.strip().split("_____")
        all_questions.setdefault(content, {}).setdefault("fillup", []).append(question)
    
    
    return render(
        request,
        "take-assessment.html",
        {
            "questions": all_questions,
            "assessment": assessment,
            "organizations": Organization.objects.get_all_cached(),
            "disabilities": Disability.objects.get_all_cached(),
            "start_time": timezone.localtime(timezone.now()).strftime("%B %d, %Y %I:%M:%S %p"),
        },
    )

def submit_assessment(request, id, slug):
    """
    Submit assessment answers for asynchronous processing.
    
    Flow:
    1. Validate assessment exists and is active
    2. Parse and validate answers JSON
    3. Create new assessment job
    4. Queue job for processing
    5. Return job ID for status tracking
    """
    client_ip = get_client_ip(request)
    logger.info(f"User {request.user} from IP {client_ip} submitting assessment {id}")

    try:
        # Validate assessment exists and is active
        if not Assessment.objects.filter(id=id, active=True).exists():
            logger.error(f"Assessment {id} not found or inactive")
            return JsonResponse({
                "success": False,
                "message": "The assessment you are trying to submit is not available."
            }, status=404)
        
        # Parse and validate answers JSON
        answers_json = request.POST.get("answers_json")
        if not answers_json:
            logger.error(f"Missing answers_json for assessment {id}")
            return JsonResponse({
                "success": False,
                "message": "There was an error while saving your assessment result."
            }, status=400)

        try:
            answers_data = json.loads(answers_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in answers: {e}")
            return JsonResponse({
                "success": False,
                "message": "Invalid assessment data format."
            }, status=400)

        # Extract and validate required fields
        email = answers_data.get("email", "").strip()
        name = answers_data.get("name", "").strip()
        
        if not email:
            logger.error(f"Missing email in assessment submission for assessment {id}")
            return JsonResponse({
                "success": False,
                "message": "Email is required to submit assessment."
            }, status=400)
        assessment_result = AssessmentResult.objects.filter(assessment__id=id, email=email).only("id").first()
        if assessment_result:
            return JsonResponse({
                "success": True,
                "message": "You have already taken the assessment.",
                "result_id": assessment_result.id
            })

        # Create new job (no duplicate checking needed)
        try:
            job = AssessmentJob.objects.create(
                assessment_id=id,
                email=email,
                job_id=str(uuid.uuid4()),
                name=name,
                status="pending",
                payload=answers_data
            )
            logger.info(f"AssessmentJob created: {job.job_id} for assessment {id}, email {email}")
            
        except Exception as e:
            logger.error(f"Database error creating job for assessment {id}: {e}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "Failed to create assessment submission. Please try again."
            }, status=500)

        # Queue job for processing
        try:
            queue_service = QueueService()
            queue_success = queue_service.send_message(job.job_id)
            
            if not queue_success:
                # Mark job as failed
                job.status = "failed"
                job.error = "Failed to queue assessment for processing"
                job.save(update_fields=['status', 'error'])
                
                logger.error(f"Queue service returned false for job {job.job_id}")
                return JsonResponse({
                    "success": False,
                    "message": "Failed to queue assessment for processing."
                }, status=500)

            logger.info(f"Assessment {id} queued successfully as job {job.job_id}")
            return JsonResponse({
                "success": True,
                "job_id": job.job_id,
            }, status=202)

        except Exception as queue_error:
            # Mark job as failed and log error
            job.status = "failed"
            job.error = f"Queue error: {str(queue_error)[:500]}"
            job.save(update_fields=['status', 'error'])
            
            logger.error(
                f"Queue submission failed for job {job.job_id}: {queue_error}",
                exc_info=True,
                extra={'assessment_id': id, 'email': email}
            )
            
            return JsonResponse({
                "success": False,
                "message": "Failed to submit assessment to processing queue. Please try again."
            }, status=500)

    except Exception as e:
        logger.error(
            f"Unexpected error in submit_assessment for assessment {id}",
            exc_info=True,
            extra={'client_ip': client_ip}
        )
        return JsonResponse({
            "success": False,
            "message": "An unexpected error occurred. Please try again later."
        }, status=500)
    

def assessment_job_status(request, job_id):
    job = AssessmentJob.objects.filter(job_id=job_id).only("status", "result_id", "error").first()

    if not job:
        return render(request, "assessment_job_status.html", {"error": "Job not found."})

    if job.status == "completed":
        return redirect("result_page", result_id=job.result_id)
    elif job.status == "failed":
        return render(request, "assessment_job_status.html", {"error": f"Job failed: {job.error}"})
    else:
        return render(request, "assessment_job_status.html", {"message": "Your assessment is being processed. Please wait..."})


def activate_deactivate_assessment(request, id):
    logger.info(f"User {request.user} is trying to activate/deactivate the assessment {id}")
    if request.user.is_anonymous or (
        not request.user.is_superuser and not request.user.is_creator
    ):
        return render(
            request,
            "home.html",
            {"error": "You are not authorized to delete this assessment"},
        )
    try:
        assessment = Assessment.objects.get(id=id, author=request.user)
    except Assessment.DoesNotExist:
        logger.error(f"Assessment with id {id} does not exist.")
        return render(
            request,
            "home.html",
            {"error": "You are not authorized to delete this assessment"},
        )
    assessment.active = not assessment.active
    assessment.save()
    if assessment.active:
        messages.success(request, "Assessment activated successfully")
    else:
        messages.success(request, "Assessment deactivated successfully")
    return redirect("assessment_list")

def assessment_list(request):
    if request.user.is_anonymous or (
        not request.user.is_superuser and not request.user.is_creator
    ):
        return render(
            request,
            "home.html",
            {
                "error": f"Welcome to the Gyanyatra portal, please login to continue, or contact your administrator for access."
            },
        )
    user = request.user
    cache_key = f"assessment_user_{user.id}"
    assessments = cache.get(cache_key)
    if assessments is None:
        # Subquery to count users per assessment
        assessments = Assessment.objects.with_metrics(
                        user=request.user,
                        include_total_questions=True,
                        include_get_user=True,
                    )
        for assessment in assessments:
            assessment.assessment_generate_url = assessment.generate_url
            assessment.assessment_maximum_marks = assessment.maximum_marks
        cache.set(cache_key, assessments, timeout=300)
    return render(request, "home.html", {"assessments": assessments,"subject":Subject.getSubjectDict()})
