import csv
from datetime import timedelta, datetime
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import render, redirect
from assessment.forms import DownloadResultsForm
from django.contrib import messages as message
from assessment.models import AssessmentResult, Answer, Subject, Assessment, Organization
from django.db.models import Count
import json
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from assessment.services.pagination import CustomPageNumberPagination
from assessment.services.calculator import safe_division
from django.db.models import F
from assessment.services.report import _build_organization_report_rows

logger = logging.getLogger('django')



def get_correct_answer(request, id):
    try:
        assessment_result = AssessmentResult.objects.get_or_filter_answer_with_prefetch(id=id,option="get")
        if not assessment_result:
            logger.error(f"AssessmentResult with id {id} does not exist.")
            return render(
                request,
                "result-correct-answer.html",
                {
                    "error": "Result not found. Please check the link or contact your administrator."
                },
            )

        user = request.user
        assessment = assessment_result.assessment
        is_privileged_user = (
            user.is_authenticated
            and (user == assessment.author or user.is_superuser)
        )

        if not assessment.show_correct_answer and not is_privileged_user:
            logger.warning(
                "Unauthorized attempt to access correct answers for AssessmentResult id %s",
                id,
            )
            return render(
                request,
                "result-correct-answer.html",
                {
                    "error": "Correct answers are not available for this assessment."
                },
            )

        answers = assessment_result.answers.all()

        # Serialize AssessmentResult manually
        result_data = {
            "name": assessment_result.name,
            "email": assessment_result.email,
            "score": assessment_result.new_score,
            "grade": assessment_result.grade,
            "total_questions": assessment_result.assessment.maximum_marks,
        }
        
        # Serialize each answer
        answer_data=[]
        for ans in answers:
            if ans.question:
                data={
                    "question": ans.question.question,
                    "options": [opt.option for opt in ans.question.options.all()],
                    "selected_option": ans.selected_option.option,
                    "correct_option": ans.question.correct_answer.option,
                    "type":"text_question",
                }
                answer_data.append(data)
            elif ans.audio_question:
                data={
                    "url": ans.audio_question.question.url,
                    "selected_option": ans.audio_answer,
                    "correct_option": ans.audio_question.answer,
                    "type":"audio_question",
                }
                answer_data.append(data)
            else:
                data={
                    "question": ans.fillup_question.sentence,
                    "selected_option": ans.fillup_answer,
                    "correct_option": ans.fillup_question.correct_answer,
                    "type":"fillup_question",
                }
                answer_data.append(data)
        return render(
            request,
            "result-correct-answer.html",
            {
                "assessment_result_json": json.dumps(result_data),
                "questions_json": json.dumps(answer_data),
            },
        )

    except Exception as e:
        logger.error(f"Error in get_correct_answer: {str(e)}")
        return render(request, "result-correct-answer.html", {
            "error": "Something went wrong."
        })


def download_pdf(request):
    logger.info("Inside download_pdf view")
    try:
        if request.POST.get('type') == "EIQ":
            self_awareness = int(request.POST.get('self_awareness'))
            managing_emotions = int(request.POST.get('managing_emotions'))
            motivating_oneself = int(request.POST.get('motivating_oneself'))
            empathy = int(request.POST.get('empathy'))
            social_skill = int(request.POST.get('social_skill'))
            name = request.POST.get('name')
            date = request.POST.get('date')

            context = {
                'self_awareness': self_awareness,
                'managing_emotions': managing_emotions,
                'motivating_oneself': motivating_oneself,
                'empathy': empathy,
                'social_skill': social_skill,
                'name': name,
                'date': date,
                'type': "EIQ",
            }

            return render(request, "download_pdf.html", context)
        elif request.POST.get('type') == "MO":
            cal_pmb = int(request.POST.get('cal_pmb'))
            cal_pmg = int(request.POST.get('cal_pmg'))
            cal_pvb = int(request.POST.get('cal_pvb'))
            cal_pvg = int(request.POST.get('cal_pvg'))
            cal_psb = int(request.POST.get('cal_psb'))
            cal_psg = int(request.POST.get('cal_psg'))
            cal_hob = int(request.POST.get('cal_hob'))
            total_B = int(request.POST.get('total_B'))
            total_G = int(request.POST.get('total_G'))
            total_G_B = int(request.POST.get('total_G_B'))
            name = request.POST.get('name')
            date = request.POST.get('date')
            disabiliity = request.POST.get('disabiliity')

            context = {
                'cal_pmb': cal_pmb,
                'cal_pmg': cal_pmg,
                'cal_pvb': cal_pvb,
                'cal_pvg': cal_pvg,
                'cal_psb': cal_psb,
                'cal_psg': cal_psg,
                'cal_hob': cal_hob,
                'total_B': total_B,
                'total_G': total_G,
                'total_G_B': total_G_B,
                'name': name,
                'date': date,
                'disabiliity': disabiliity,
            }
            return render(request, "download_pdf_mo.html", context)
        elif request.POST.get('type') == "FS":
            dismissing = float(request.POST.get('dismissing_percent'))
            disapproving = float(request.POST.get('disapproving_percent'))
            laissez_faire = float(request.POST.get('laissez_faire_percent'))
            emotion_coaching = float(request.POST.get('emotion_coaching_percent'))
            name = request.POST.get('name')
            date = request.POST.get('date')

            context = {
                'dismissing': dismissing,
                'disapproving': disapproving,
                'laissez_faire': laissez_faire,
                'emotion_coaching': emotion_coaching,
                'name': name,
                'date': date,
            }
            return render(request, "download_pdf_fs.html", context)
    except (TypeError, ValueError) as e:
        # If any value is missing or not convertible to int
        logger.error(f"Error in download_pdf view: {str(e)}")
    
    except Exception as e:
        # For any other unexpected error
        logger.error(f"Unexpected error in download_pdf view: {str(e)}")


def assessment_results(request, id):
    logger.info("Inside assessment_results view")
    if request.user.is_anonymous or (
        not request.user.is_superuser and not request.user.is_creator
    ):
        return render(
            request,
            "home.html",
            {
                "error": "Welcome to the assessment portal, please login to continue, or contact your administrator for access."
            },
        )
    return render(request, "assessment-results.html", { "id": id, "subject_labels": Subject.getSubjectDict(),})


def organization_report(request):
    logger.info("Inside organization_report view")
    if request.user.is_anonymous or (
        not request.user.is_superuser and not request.user.is_creator
    ):
        return render(
            request,
            "home.html",
            {
                "error": "Welcome to the assessment portal, please login to continue, or contact your administrator for access."
            },
        )
    
    today = timezone.localdate()
    default_start_date = today - timedelta(days=6)
    default_end_date = today

    assessments = list(
        Assessment.objects.filter(author=request.user)
        .order_by("name")
        .values("id", "name")
        
    )
    organizations = list(
        Organization.objects.filter(assessmentresult__assessment__author=request.user)
        .order_by("name")
        .values("id", "name")
        .distinct()
    )
    default_rows = _build_organization_report_rows(
        user=request.user,
        start_date=default_start_date,
        end_date=default_end_date,
    )

    return render(
        request,
        "organization-report.html",
        {
            "assessments": assessments,
            "organizations": organizations,
            "default_start_date": default_start_date.strftime("%Y-%m-%d"),
            "default_end_date": default_end_date.strftime("%Y-%m-%d"),
            "default_rows_json": json.dumps(default_rows),
        },
    )


@api_view(["GET"])
def get_organization_report_data(request):
    logger.info("Inside get_organization_report_data API view")
    if request.user.is_anonymous or (
        not request.user.is_superuser and not request.user.is_creator
    ):
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    assessment_id = request.GET.get("assessment_id")
    organization_id = request.GET.get("organization_id")

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else None
    except (TypeError, ValueError):
        start_date = None

    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
    except (TypeError, ValueError):
        end_date = None

    if start_date and end_date and start_date > end_date:
        return Response({"error": "start_date cannot be greater than end_date"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        assessment_id = int(assessment_id) if assessment_id else None
    except (TypeError, ValueError):
        assessment_id = None
    try:
        organization_id = int(organization_id) if organization_id else None
    except (TypeError, ValueError):
        organization_id = None

    data = _build_organization_report_rows(
        user=request.user,
        start_date=start_date,
        end_date=end_date,
        assessment_id=assessment_id,
        organization_id=organization_id,
    )
    return Response({"results": data}, status=status.HTTP_200_OK)

@api_view(['GET'])
def get_assessment_results(request, id):
    logger.info("Inside get_assessment_results API view")
    user = request.user
    meta_cache_key = f'assessment_results_meta_user_{user.id}_assessment_{id}'
    question_type_cache_key = f'assessment_question_types_{id}'

    try:
        cached_payload = cache.get(meta_cache_key)
        if cached_payload is None:
            # Single query to get assessment with all required fields
            assessment = (
                Assessment.objects.filter(id=id, author=user)
                .only("id", "level", "subject", "sub_level", "name")
                .first()
            )
            if not assessment:
                logger.error(f"No Assessment found for assessment {id}.")
                return Response({"error": "No results found."}, status=status.HTTP_404_NOT_FOUND)

            # Early exit: check if results exist before building cache
            has_results = AssessmentResult.objects.filter(
                assessment__author=user,
                assessment__id=id,
            ).exists()
            if not has_results:
                logger.error(f"No AssessmentResult found for assessment {id}.")
                return Response({"error": "No results found."}, status=status.HTTP_404_NOT_FOUND)

            # Get question types from cache or fetch once
            total_question_type = cache.get(question_type_cache_key)
            if total_question_type is None:
                total_question_type = list(
                    Assessment.objects.filter(id=id)
                    .values("questions__category")
                    .annotate(count=Count("questions__id"))
                )
                # Cache question types with longer timeout (1 day)
                cache.set(question_type_cache_key, total_question_type, timeout=86400)

            cached_payload = {
                "assessment_type": assessment.level,
                "assessment_max_marks": assessment.maximum_marks,
                "total_question_type": total_question_type,
            }
            cache.set(meta_cache_key, cached_payload, timeout=300)

        results_queryset = (
            AssessmentResult.objects.filter(
                assessment__author=user,
                assessment__id=id,
            )
            .select_related("assessment", "organization")
            .annotate(
                organization_name=F("organization__name"),
                assessment_name=F("assessment__name"),
                assessment_level=F("assessment__level"),
                assessment_subject=F("assessment__subject"),
                assessment_sub_level=F("assessment__sub_level"),
            )
            .values(
                "id",
                "name",
                "email",
                "education",
                "score",
                "new_score",
                "grade",
                "total_questions",
                "attempted_questions",
                "start_time",
                "end_time",
                "date",
                "assessment_id",
                "disabiliity_id",
                "organization_name",
                "assessment_name",
                "assessment_level",
                "assessment_subject",
                "assessment_sub_level",
            )
            .order_by("id")
        )
    except Exception as e:
        logger.error(f"Error fetching assessment results for assessment {id}: {str(e)}")
        return Response({"error": "No results found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(results_queryset, request)
    except Exception as e:
        logger.error(f"Error during pagination: {str(e)}")
        return Response({"error": "An error occurred while paginating results."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = paginator.get_paginated_response({
        "results": list(page),
        "assessment_type": cached_payload["assessment_type"],
        "assessment_max_marks": cached_payload["assessment_max_marks"],
        "assessment_id": id,
        "total_question_type": cached_payload["total_question_type"],
    })
    logger.info(f"get_assessment_results API view completed successfully")

    return data


def result_page(request, result_id):
    try:
        assessment_result = (
            AssessmentResult.objects.get_or_filter_answer_with_prefetch(id=result_id,option="get")
        )
    except AssessmentResult.DoesNotExist:
        assessment_result = None
        logger.error(f"AssessmentResult with id {result_id} does not exist.")
        return render(
            request,
            "home.html",
            {
                "error": "Result not found. Please check the link or contact your administrator."
            },
        )
    if assessment_result.assessment.level =="LS1EIQ1":
        assessment_answer = assessment_result.answers.all()
        total_question_type=assessment_answer.values('question__category').annotate(count=Count('id'))
        return render(
            request,
            "result-page-ls1eiq1.html",
            {
                "assessment_result": assessment_result,
                "total_question_type": json.dumps(list(total_question_type)),
            },
        )
    if assessment_result.assessment.level =="LS1MO1":
        return render(
            request,
            "result-page-ls1mo1.html",
            {
                "assessment_result": assessment_result
            },
        )
    if assessment_result.assessment.level =="LS1FS1":
        assessment_answer = assessment_result.answers.all()
        total_question_type=assessment_answer.values('question__category').annotate(count=Count('id'))
        return render(
            request,
            "result-page-ls1fs1.html",
            {
                "assessment_result": assessment_result,
                "total_question_type": json.dumps(list(total_question_type)),
            },
        )

    else:
        return render(
            request,
            "result-page.html",
            {
                "assessment_result": assessment_result,
                "subject": Subject.getSubjectDict(),
            },
        )





def download_results_csv(request):
    logger.info("Inside download_results_csv view")
    try:
        if request.user.is_anonymous or (
            not request.user.is_superuser and not request.user.is_creator
        ):
            return render(
                request,
                "home.html",
                {
                    "error": "Welcome to the assessment portal, please login to continue, or contact your administrator for access."
                },
            )

        if request.method == "POST":
            form = DownloadResultsForm(request.user, request.POST)
            if form.is_valid():
                assessment = form.cleaned_data["assessment"]
                organization = form.cleaned_data["organization"]
                include_qna = form.cleaned_data["include_qna"]
                if organization:
                    results = (
                        AssessmentResult.objects.get_or_filter_answer_with_prefetch(assessment__author=request.user, assessment=assessment, organization=organization,option="filter")
                        .order_by("id")
                    )
                else:
                    results = (
                        AssessmentResult.objects.get_or_filter_answer_with_prefetch(assessment__author=request.user, assessment=assessment,option="filter")
                        .order_by("id")
                    )
            else:
                # If the form is not submitted or not valid, download all results
                results = (
                    AssessmentResult.objects.get_or_filter_answer_with_prefetch(assessment__author=request.user, assessment=assessment,option="filter")
                    .order_by("id")
                )

            if not results:
                message.error(
                    request, "No results found for selected assessment and organization."
                )
                return redirect("download_results_csv")

            response = HttpResponse(content_type="text/csv")
            response[
                "Content-Disposition"
            ] = f'attachment; filename="results-{assessment.name.split()[0]}.csv"'

            writer = csv.writer(response)
            return download_results(writer, results, response, include_qna)
        else:
            form = DownloadResultsForm(request.user)

        return render(request, "download-report.html", {"form": form})
    except Exception as e:
        logger.error(f"Error in download_results_csv view: {str(e)}")
        message.error(request, "An error occurred while processing your request.")
        return redirect("download_results_csv")


def download_results(writer, results, response, include_qna=False):
    logger.info("Inside download_results function")
    assessment_type= results.first().assessment.level
    if assessment_type == "LS1EIQ1":
        first = [
                "Name",
                "Email",
                "Education",
                "Disability",
                "Assessment",
                "Institute",
                "Subject",
                "Self awareness",
                "Managing emotions",
                "Motivating oneself",
                "Empathy",
                "Social Skill",
                "Start Time",
                "End Time",
                "Duration",
                "View Result"
            ]
    elif assessment_type == "LS1MO1":
        first = [
                "Name",
                "Email",
                "Education",
                "Disability",
                "Assessment",
                "Institute",
                "Subject",
                "PmB",
                "PmG",
                "PvB",
                "PvG",
                "HoB",
                "PsB",
                "PsG)",
                "Total B",
                "Total G",
                "Total G-B",
                "Start Time",
                "End Time",
                "Duration",
                "View Result"
            ]
    elif assessment_type == "LS1FS1":
        first = [
                "Name",
                "Email",
                "Education",
                "Disability",
                "Assessment",
                "Institute",
                "Subject",
                "Dismissing",
                "Disapproving",
                "Laissez Faire",
                "Emotion Coaching",
                "Start Time",
                "End Time",
                "Duration",
                "View Result"
            ]
    else:
        first = [
                "Name",
                "Email",
                "Education",
                "Disability",
                "Assessment",
                "Institute",
                "Subject",
                "Maximum Marks",
                "Marks Obtained",
                "Grade",
                "Start Time",
                "End Time",
                "Duration",
                "View Result"
            ]

    if include_qna:
        first += [question.question for question in results[0].assessment.questions.all().order_by("id")] 
        writer.writerow(first)
        writer.writerow(
            [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ] + [question.correct_answer.option for question in results[0].assessment.questions.all().order_by("id")]
        )
        writer.writerow([])
    else:
        writer.writerow(first)
    for result in results:
        if assessment_type == "LS1EIQ1":
            second = [  
                result.name,
                result.email,
                result.education if result.education else "None",
                result.disabiliity.name if result.disabiliity else "None",
                result.assessment.name,
                result.organization,
                Subject.getlabel(result.assessment.subject),
                result.new_score['SA'],
                result.new_score['ME'],
                result.new_score['MO'],
                result.new_score['EP'],
                result.new_score['SS'],
                timezone.localtime(result.start_time).strftime("%B %d, %Y %I:%M:%S %p"),
                timezone.localtime(result.end_time).strftime("%B %d, %Y %I:%M:%S %p"),
                result.end_time - result.start_time,
                result.generate_url

                ]
            
        elif assessment_type == "LS1MO1":
            second = [  
                result.name,
                result.email,
                result.education if result.education else "None",
                result.disabiliity.name if result.disabiliity else "None",
                result.assessment.name,
                result.organization,
                Subject.getlabel(result.assessment.subject),
                result.new_score['PmB'],
                result.new_score['PmG'],
                result.new_score['PvB'],
                result.new_score['PvG'],
                result.new_score['PvB'] + result.new_score['PmB'],
                result.new_score['PsB'],
                result.new_score['PsG'],
                result.new_score['PmB'] + result.new_score['PvB'] + result.new_score['PsB'],
                result.new_score['PmG'] + result.new_score['PvG'] + result.new_score['PsG'],
                result.new_score['PmG'] + result.new_score['PvG'] + result.new_score['PsG'] - (result.new_score['PmB'] + result.new_score['PvB'] + result.new_score['PsB']),
                timezone.localtime(result.start_time).strftime("%B %d, %Y %I:%M:%S %p"),
                timezone.localtime(result.end_time).strftime("%B %d, %Y %I:%M:%S %p"),
                result.end_time - result.start_time,
                result.generate_url
            ]
        elif assessment_type == "LS1FS1":
            assessment_answer=result.answers.all()
            total_question_type = {
                item['question__category']: item['count']
                for item in assessment_answer.values('question__category').annotate(count=Count('id'))
            }
            second = [  
                result.name,
                result.email,
                result.education if result.education else "None",
                result.disabiliity.name if result.disabiliity else "None",
                result.assessment.name,
                result.organization,
                Subject.getlabel(result.assessment.subject),
                safe_division(result.new_score.get('DM', 0), total_question_type.get('DM', 0)),
                safe_division(result.new_score.get('DAP', 0), total_question_type.get('DAP', 0)),
                safe_division(result.new_score.get('LF', 0), total_question_type.get('LF', 0)),
                safe_division(result.new_score.get('EC', 0), total_question_type.get('EC', 0)),
                timezone.localtime(result.start_time).strftime("%B %d, %Y %I:%M:%S %p"),
                timezone.localtime(result.end_time).strftime("%B %d, %Y %I:%M:%S %p"),
                result.end_time - result.start_time,
                result.generate_url
            ]
        else:
            second = [  
                result.name,
                result.email,
                result.education if result.education else "None",
                result.disabiliity.name if result.disabiliity else "None",
                result.assessment.name,
                result.organization,
                Subject.getlabel(result.assessment.subject),
                result.assessment.maximum_marks,
                result.new_score['total_score'],
                result.grade,
                timezone.localtime(result.start_time).strftime("%B %d, %Y %I:%M:%S %p"),
                timezone.localtime(result.end_time).strftime("%B %d, %Y %I:%M:%S %p"),
                result.end_time - result.start_time,
                result.generate_url
                ]

        
        if include_qna:
            second += [answer.selected_option.option for answer in result.answers.all().order_by("question__id")]
        writer.writerow(second)

    return response
