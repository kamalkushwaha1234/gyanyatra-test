import logging
logger = logging.getLogger("django")
from django.core.cache import cache
from assessment.models import (
    Assessment,
    Disability,
    Organization,
    Question,
    Answer,
    AssessmentResult,
    Category,
)
from django.db.models import Prefetch
from datetime import datetime
from django.utils import timezone
from assessment.grading import GRADING
from django.db import transaction

def process_assessment(job):
    """Process assessment job from queue without Flask/Django request context.
    This function is called by the worker and should not return HTTP responses.
    Returns the assessment_result.id on success, raises exception on failure.
    """
    answers_data = job.payload
    assessment_id = job.assessment_id
    
    # Extract variables from job payload
    name = answers_data.get("name")
    email = answers_data.get("email")
    edu = answers_data.get("education")
    organization = answers_data.get("organization")
    disability = answers_data.get("disability")
    start_time_str = answers_data.get("start_time")
    
    logger.info(f"Processing assessment job {job.job_id} for assessment {assessment_id}")

    try:
        # Fetch assessment with prefetched data
        cache_key = f"assessment_{assessment_id}"
        assessment = cache.get(cache_key)
        if not assessment:
            assessment = Assessment.objects.prefetch_related(
                Prefetch(
                    "questions",
                    queryset=Question.objects.prefetch_related(
                        Prefetch("options", to_attr="prefetched_options")
                    ),
                    to_attr="prefetched_questions"
                ),
                Prefetch("audio_questions", to_attr="prefetched_audio_questions"),
                Prefetch("fillup_questions", to_attr="prefetched_fillup_questions"),
            ).get(id=assessment_id)
            cache.set(cache_key, assessment, timeout=3600)
        logger.info(f"Assessment {assessment_id} found. Level: {assessment.level}")
        
        # Initialize scores based on assessment level
        if assessment.level in ['LS1EIQ1', 'LS1MO1', 'LS1FS1']:
            categories = Category.getLevelCategory(level=assessment.level)
            new_score = {cat["name"]: 0 for cat in categories}
        else:
            new_score = {"total_score": 0}

        # Try to get cached question dictionaries
        cache_key_dicts = f"assessment_question_{assessment_id}"
        dicts = cache.get(cache_key_dicts)

        if dicts:
            logger.info(f"Using cached question dictionaries for assessment {assessment_id}")
            question_dict = dicts["question_dict"]
            options_dict = dicts["options_dict"]
            correct_option_dict = dicts["correct_option_dict"]
            fillup_dict = dicts["fillup_dict"]
            audio_dict = dicts["audio_dict"]
        else:
            logger.info(f"Building question dictionaries for assessment {assessment_id}")
            # Build dictionaries in memory
            question_dict = {q.id: q for q in assessment.prefetched_questions}
            options_dict = {q.id: {opt.id: opt for opt in q.prefetched_options} for q in assessment.prefetched_questions}
            correct_option_dict = {
                q.id: next((opt.id for opt in q.prefetched_options if opt.is_correct), None)
                for q in assessment.prefetched_questions
            }
            fillup_dict = {q.id: q for q in assessment.prefetched_fillup_questions}
            audio_dict = {q.id: q for q in assessment.prefetched_audio_questions}

            # Cache for future requests (e.g., 1 hour)
            cache.set(cache_key_dicts, {
                "question_dict": question_dict,
                "options_dict": options_dict,
                "correct_option_dict": correct_option_dict,
                "fillup_dict": fillup_dict,
                "audio_dict": audio_dict
            }, timeout=3600)

        # Process answers
        ans_list = []
        for q_data in answers_data.get("answers", []):
            q_type = q_data.get("type")
            q_id = int(q_data.get("id"))

            if q_type == "mcq":
                question = question_dict[q_id]
                selected_option_id = int(q_data.get("selected_option", -1))
                selected_option = options_dict[q_id].get(selected_option_id)
                question_score = 0

                correct_id = correct_option_dict[q_id]
                if selected_option:
                    if assessment.level == "LS1EIQ1":
                        question_score = int(selected_option.option)
                        new_score[question.category] += question_score
                    elif assessment.level in ["LS1MO1", "LS1FS1"]:
                        question_score = 1 if selected_option_id == correct_id else 0
                        new_score[question.category] += question_score
                    else:
                        question_score = 1 if selected_option_id == correct_id else 0
                        new_score["total_score"] += question_score
                else:
                    ans_list[-1].is_correct = False
                ans_list.append(Answer(question=question, selected_option=selected_option, is_correct=selected_option_id == correct_id, mark_obtained=question_score))

            elif q_type == "fillup":
                question = fillup_dict[q_id]
                user_answers = q_data.get("answers", {})
                correct_answers = question.correct_answer
                points = sum(1 for k in correct_answers if correct_answers.get(k) == user_answers.get(k))
                ans_list.append(Answer(fillup_question=question, fillup_answer=user_answers, mark_obtained=points, is_correct=points == len(correct_answers)))
                new_score["total_score"] += points

            elif q_type == "audio":
                question = audio_dict[q_id]
                audio_answer = q_data.get("audio_answer", "").strip()
                if audio_answer:
                    point, _, status = question.is_correct(audio_answer)
                    ans_list.append(Answer(audio_question=question, audio_answer=audio_answer, mark_obtained=point, is_correct=status))
                    new_score["total_score"] += point


        # Create AssessmentResult
        obtained_marks = sum(new_score.values()) if assessment.level in ['LS1EIQ1', 'LS1MO1', 'LS1FS1'] else int(new_score["total_score"])
        score = round(90 * (obtained_marks / assessment.maximum_marks)) if obtained_marks > 0 else 0
        assessment_grade = next((grade for grade, g in GRADING.items() if score in g.range), None) or "A1"

        attempted_questions = int(answers_data.get("attempted_count", 0))
        
        # Parse start_time from string
        try:
            start_time = datetime.strptime(start_time_str, "%B %d, %Y %I:%M:%S %p")
            start_time = timezone.make_aware(start_time)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse start_time {start_time_str}, using current time")
            start_time = timezone.localtime(timezone.now())
        
        with transaction.atomic():
            # Bulk create answers
            logger.info(f"Bulk creating {len(ans_list)} answers for job {job.job_id}")
            created_answers = Answer.objects.bulk_create(ans_list)

            assessment_result = AssessmentResult.objects.create(
                assessment=assessment,
                name=name,
                email=email,
                education=edu,
                organization=Organization(id=organization) if organization else None,
                disabiliity=Disability(id=disability) if disability else None,
                grade=assessment_grade,
                total_questions=attempted_questions,
                attempted_questions=attempted_questions,
                start_time=start_time,
                end_time=job.created_at,
                new_score=new_score,
                score=0,
            )

            # Attach answers
            ThroughModel = AssessmentResult.answers.through
            m2m_objects = [
                ThroughModel(
                    assessmentresult_id=assessment_result.id, 
                    answer_id=ans.id
                ) for ans in created_answers
            ]
            ThroughModel.objects.bulk_create(m2m_objects)
            logger.info(f"AssessmentResult {assessment_result.id} created for job {job.job_id}")

        return assessment_result.id

    except Assessment.DoesNotExist:
        logger.error(f"Assessment {assessment_id} not found for job {job.job_id}")
        raise
    except Exception as e:
        logger.error(f"Transaction failed for job {job.job_id}, assessment {assessment_id}: {e}", exc_info=True)
        raise