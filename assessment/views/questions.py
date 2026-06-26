import logging
import base64
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q, Exists, OuterRef
from django.http import JsonResponse, HttpResponse
import json
from assessment.models import ASSESSMENT_LEVELS, Content, Question, Option, Subject, AudioQuestion,Category,FillInTheBlank,SUB_LEVELS,Assessment,MAP_SUBLEVELS_TO_SUBJECT
from assessment.services.curd_question import create_row_fillup_question, create_row_audio_question, create_row_text_question,delete_question
from assessment.services.question_importer import validate_and_prepare_import, build_sample_template_workbook_bytes
logger = logging.getLogger('django')


def process_question_form(request, id=None):
    logger.info(f"Inside process_question_form view with id: {id}")
    if request.user.is_anonymous or (not request.user.is_superuser
                                     and not request.user.is_creator):
        return render(request, "home.html", {
            "error": "Welcome to assessment portal. Please login to continue. Or contact your administrator for access."
        })
    # If id is provided, fetch the content and related questions
    # If id is not provided, initialize empty content and questions
    user_content_qs = None
    user_question_qs = []
    user_audio_question_qs = []
    user_fillup_question_qs = []
    user_categorie_qs = Category.getCategoryWithLevel()
    having_assessment = False

    if id:
        try:
            user_content_qs = Content.objects.get(id=id)
        except Content.DoesNotExist:
            logger.error(f"Content with id {id} does not exist.")
            return render(request, "home.html", {
                "error": "Content not found."
            })
        user_question_qs = Question.objects.filter(
            content=user_content_qs,
            author=request.user
        ).annotate(
            having_assessment=Exists(
                Assessment.objects.filter(questions__id=OuterRef("id"))
            )
        ).order_by("id")

        # Audio Questions
        user_audio_question_qs = AudioQuestion.objects.filter(
            content=user_content_qs,
            author=request.user
        ).annotate(
            having_assessment=Exists(
                Assessment.objects.filter(audio_questions__id=OuterRef("id"))
            )
        ).order_by("id")

        # Fill in the Blanks
        user_fillup_question_qs = FillInTheBlank.objects.filter(
            content=user_content_qs,
            author=request.user
        ).annotate(
            having_assessment=Exists(
                Assessment.objects.filter(fillup_questions__id=OuterRef("id"))
            )
        ).order_by("id")
        having_assessment = user_question_qs.filter(
            having_assessment=True).exists() or user_audio_question_qs.filter(
                having_assessment=True).exists() or user_fillup_question_qs.filter(
                    having_assessment=True).exists()
        user_categorie_qs = Category.getCategoryWithLevel()
    if user_question_qs and user_question_qs[0].level:
        selectedlevel = user_question_qs[0].level
        selectedsubject = user_question_qs[0].subject
        selectedsublevel = user_question_qs[0].sub_level
    elif user_audio_question_qs and user_audio_question_qs[0].level:
        selectedlevel = user_audio_question_qs[0].level
        selectedsubject = user_audio_question_qs[0].subject
        selectedsublevel = user_audio_question_qs[0].sub_level
    elif user_fillup_question_qs and user_fillup_question_qs[0].level:
        selectedlevel = user_fillup_question_qs[0].level
        selectedsubject = user_fillup_question_qs[0].subject
        selectedsublevel = user_fillup_question_qs[0].sub_level
    else:
        selectedlevel = ASSESSMENT_LEVELS[0][0]
        selectedsubject = Subject.ENGLISH.value
        selectedsublevel = None
    excluded_sub_levels = [Subject.LIFE_SKILL.value]
    # If the request method is POST, process the form data
    if request.method == "POST":
        new_content_created = False
        content_text = request.POST.get("content").strip()
        if id:
            if content_text and user_content_qs and content_text != user_content_qs.content:
                user_content_qs.content = content_text
                user_content_qs.save(update_fields=["content"])
        else:
            user_content_qs = Content.objects.create(content=content_text)
            new_content_created = True
        # Get the form data from the request
        # This includes options, correct answers, categories, audio answers,
        #  and audio files
        # general data
        content_level = request.POST.get("level")
        content_subLevel = request.POST.get("sub_level")
        content_subject = request.POST.get("subject")
        if content_subject in excluded_sub_levels:
            content_subLevel = ""
        """
        levels_with_multiple_categories list help to when we want to save the
        categories or not
        """
        levels_with_multiple_categories = ["LS1EIQ1", "LS1FS1", "LS1MO1"]
        """
        custom_calculation_levels list help when we want to check the
        correct option for question
        """
        custom_calculation_levels = ["LS1EIQ1"]
        categorie_list = request.POST.getlist("category")

        # for text questions
        option1_list = request.POST.getlist("option1")
        option2_list = request.POST.getlist("option2")
        option3_list = request.POST.getlist("option3")
        option4_list = request.POST.getlist("option4")
        option5_list = request.POST.getlist("option5")
        correct_option_list = request.POST.getlist("correct")
        list_upcoming_question = []

        # for audio questions
        audio_answer_list = request.POST.getlist("audio-answer")
        audio_question_file_dict = [{f"{i.split('-')[-1]}":request.FILES[i]} for i in request.FILES]
        audio_question_id_list = request.POST.getlist('audio-id')
        list_upcoming_audio_question = []

        # for fillup questions
        blanks_list = [request.POST.getlist("blank1"), request.POST.getlist("blank2"), request.POST.getlist("blank3"),
                       request.POST.getlist("blank4"), request.POST.getlist("blank5"), request.POST.getlist("blank6"),
                       request.POST.getlist("blank7"), request.POST.getlist("blank8"), request.POST.getlist("blank9"),
                       request.POST.getlist("blank10")]
        list_upcoming_fillup_question = []

        try:
            question_ids = user_question_qs.values_list('id', flat=True)
        except Exception as e:
            logger.error(f"Error fetching question ids: {e}")
            question_ids = []
        try:
            fillup_question_ids = user_fillup_question_qs.values_list('id', flat=True)
        except Exception as e:
            logger.error(f"Error fetching fillup question ids: {e}")
            fillup_question_ids = []
        
        # for delete the audio_questions
        audio_id_list = [i.split("aq_")[1] for i in audio_question_id_list if "new" not in i]
        user_audio_question_qs = delete_question(user_audio_question_qs, audio_id_list)

        # for delete the text question
        question_ids_changes = request.POST.getlist('question_id')
        user_question_qs = delete_question(user_question_qs, question_ids_changes)

        # for delete the fillup question
        fillup_ids = request.POST.getlist('fillup_id')
        user_fillup_question_qs = delete_question(user_fillup_question_qs,
                                                  fillup_ids)
        
        # update the content level, sublevel and subject for existing questions
        if selectedlevel != content_level and not new_content_created:
            user_question_qs.update(level=content_level)
            user_audio_question_qs.update(level=content_level)
            user_fillup_question_qs.update(level=content_level)
        if selectedsublevel != content_subLevel and not new_content_created:
            user_question_qs.update(sub_level=content_subLevel)
            user_audio_question_qs.update(sub_level=content_subLevel)
            user_fillup_question_qs.update(sub_level=content_subLevel)
        if selectedsubject != content_subject and not new_content_created:
            user_question_qs.update(subject=content_subject)
            user_audio_question_qs.update(subject=content_subject)
            user_fillup_question_qs.update(subject=content_subject)

        # for create upcoming list of text question
        for ind, ques in enumerate(request.POST.getlist('question')):
            if ques.strip():
                list_upcoming_question.append(("question", ques.strip()))

        # for create upcoming list of fillup question
        for ind, ques in enumerate(request.POST.getlist('fillup')):
            if ques.strip():
                list_upcoming_fillup_question.append(("fillup", ques.strip()))

        # for create upcoming list of audio_question
        try:
            for ind, value in enumerate(audio_question_id_list):
                if "new" not in value:
                    if audio_question_file_dict and audio_question_file_dict[0].get(str(value), False):
                        # if question is not new but the audio file is changed
                        list_upcoming_audio_question.append((f"aq_{user_audio_question_qs[ind].id}",audio_question_file_dict[0][value]))
                        audio_question_file_dict.pop(0)
                    else:
                        list_upcoming_audio_question.append((f"aq_{user_audio_question_qs[ind].id}",user_audio_question_qs[ind].question))
                else:
                    list_upcoming_audio_question.append((value, audio_question_file_dict[0][value]))
                    audio_question_file_dict.pop(0)
        except Exception as e:
            logger.error(f"Error creating upcoming audio questions: {e}")

        # create and update fillup questions
        logger.info("Creating/updating fillup questions")
        create_row_fillup_question(request.user, id,
                                   list_upcoming_fillup_question,
                                   user_fillup_question_qs, blanks_list,
                                   fillup_question_ids, fillup_ids,
                                   content_level, content_subLevel,
                                   content_subject, user_content_qs)
        
        # for creating audio question
        logger.info("Creating/updating audio questions")
        create_row_audio_question(request.user, id,
                                  list_upcoming_audio_question,
                                  user_audio_question_qs,
                                  audio_question_id_list,
                                  content_level, content_subLevel,
                                  content_subject, user_content_qs,
                                  audio_answer_list)
        
        # for creating text question
        logger.info("Creating/updating text questions")
        create_row_text_question(request.user, id,
                                 list_upcoming_question,
                                 user_question_qs, question_ids_changes,
                                 question_ids, option1_list, option2_list,
                                 option3_list, option4_list, option5_list,
                                 content_level, content_subLevel,
                                 content_subject, user_content_qs,
                                 correct_option_list,
                                 levels_with_multiple_categories,
                                 custom_calculation_levels, categorie_list)
        user_content_qs.save()
        return redirect("display_all_questions")
    return render(
        request,
        "add-edit-content.html",
        {
            "title": "Edit Content" if id else "Add Content",
            "edit": True if id else False,
            "content": user_content_qs,
            "questions": user_question_qs,
            "audio_questions": user_audio_question_qs,
            "fillup_questions": user_fillup_question_qs,
            "subjects": Subject.getSubjectDict(),
            "levels": ASSESSMENT_LEVELS,
            "sub_levels": SUB_LEVELS,
            "categories": user_categorie_qs,
            "selectedlevel": selectedlevel,
            "selectedsubject": selectedsubject,
            "selectedsublevel":selectedsublevel,
            "having_assessment": having_assessment,
            "MAP_SUBLEVELS_TO_SUBJECT":json.dumps(MAP_SUBLEVELS_TO_SUBJECT),
        },
    )


def display_all_questions(request):
    logger.info(f"Inside display_all_questions view ")
    if request.user.is_anonymous or (not request.user.is_superuser and not request.user.is_creator):
        return render(request, "home.html",{"error":"Welcome to assessment portal. Please login to continue. Or contact your administrator for access."})

    questions_with_content = Question.objects.select_related("content").filter(author=request.user).order_by("id")
    audio_questions_with_content = AudioQuestion.objects.select_related("content").filter(author=request.user).order_by("id")
    fillup_questions_with_content = FillInTheBlank.objects.select_related("content").filter(author=request.user).order_by("id")

    content_questions_list = []

    for question in questions_with_content:
        content = question.content
        content_data = next(
            (item for item in content_questions_list if item["content"] == content),
            None,
        )

        if not content_data:
            content_data = {"content": content, "questions": []}
            content_questions_list.append(content_data)

        content_data["questions"].append(question)

    for question in fillup_questions_with_content:
        content = question.content
        content_data = next(
            (item for item in content_questions_list if item["content"] == content),
            None,
        )

        if not content_data:
            content_data = {"content": content, "questions": []}
            content_questions_list.append(content_data)
        content_data["questions"].append(question)

    for question in audio_questions_with_content:
        content = question.content
        content_data = next(
            (item for item in content_questions_list if item["content"] == content),
            None,
        )

        if not content_data:
            content_data = {"content": content, "questions": []}
            content_questions_list.append(content_data)
        content_data["questions"].append(question)


    return render(
        request,
        "display-all-questions.html",
        {
            "content_questions_list": content_questions_list,
            "levels": ASSESSMENT_LEVELS,
            "subjects": Subject.getSubjectDict(),
        },
    )


def import_questions_preview_api(request):
    if request.user.is_anonymous or (not request.user.is_superuser and not request.user.is_creator):
        return JsonResponse(
            {
                "success": False,
                "message": "Unauthorized user.",
            },
            status=403,
        )

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed.",
            },
            status=405,
        )

    template_file = request.FILES.get("template_file")
    if not template_file:
        return JsonResponse(
            {
                "success": False,
                "message": "Template file is required.",
            },
            status=400,
        )

    try:
        import_result = validate_and_prepare_import(template_file, source_name=template_file.name)
    except Exception as exc:
        logger.error("Error while validating import template: %s", exc, exc_info=True)
        return JsonResponse(
            {
                "success": False,
                "message": "Unable to parse import file.",
            },
            status=400,
        )

    if not import_result.is_valid:
        encoded_file = ""
        if import_result.error_file_bytes:
            encoded_file = base64.b64encode(import_result.error_file_bytes).decode("utf-8")
        return JsonResponse(
            {
                "success": False,
                "message": import_result.message,
                "errors": import_result.error_messages,
                "error_file_name": import_result.error_file_name,
                "error_file_base64": encoded_file,
            },
            status=400,
        )

    meta = import_result.normalized_meta
    return JsonResponse(
        {
            "success": True,
            "message": "Import successful",
            "content": meta.get("content", ""),
            "level": meta.get("level", ""),
            "subject": meta.get("subject", ""),
            "sub_level": meta.get("sub_level", ""),
            "questions": import_result.preview_questions,
        }
    )


def import_questions_sample_template_api(request):
    if request.user.is_anonymous or (not request.user.is_superuser and not request.user.is_creator):
        return JsonResponse(
            {
                "success": False,
                "message": "Unauthorized user.",
            },
            status=403,
        )

    if request.method != "GET":
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed.",
            },
            status=405,
        )

    workbook_bytes = build_sample_template_workbook_bytes()
    response = HttpResponse(
        workbook_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="questions_template.xlsx"'
    return response
