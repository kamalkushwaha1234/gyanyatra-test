import logging
from django.db.models import Count, Case, When, IntegerField, Sum,Q
from django.db.models.functions import Cast
from django.db.models.expressions import RawSQL
from assessment.models import Question, Answer, FillInTheBlank, AudioQuestion
logger = logging.getLogger("django")

def ReEvaluation(results,assessment_type):
    '''
    This function recalculates the scores for each `AssessmentResult` in the `results` queryset 
    using an appropriate scoring algorithm depending on the `assessment_type`. 
    The calculated scores are then updated in the `score` field of each result instance and saved to the database

    '''
    logger.info("Inside the ReEvaluation function")
    try:
        for result in results:
            result.new_score = {}
            if assessment_type == "LS1EIQ1":
                cal_score=calculate_marks_lseqi(result)
                result.new_score['SA']=cal_score['self_awareness']
                result.new_score['ME']=cal_score['managing_emotions']
                result.new_score['MO']=cal_score['motivating_oneself']
                result.new_score['EP']=cal_score['empathy']
                result.new_score['SS']=cal_score['social_skill']
            elif assessment_type== "LS1MO1":
                cal_score=calculate_marks_lsmo(result)
                result.new_score['PmB']=cal_score['cal_pmb']
                result.new_score['PmG']=cal_score['cal_pmg']
                result.new_score['PvB']=cal_score['cal_pvb']
                result.new_score['PvG']=cal_score['cal_pvg']
                result.new_score['PsB']=cal_score['cal_psb']
                result.new_score['PsG']=cal_score['cal_psg']
            elif assessment_type== "LS1FS1":
                cal_score=calculate_marks_lsfs(result)
                result.new_score['DM']=cal_score['dismissing']
                result.new_score['DAP']=cal_score['disapproving']
                result.new_score['LF']=cal_score['laissez_faire']
                result.new_score['EC']=cal_score['emotion_coaching']
            else:
                cal_score = calculate_marks_general(result)
                result.new_score['total_score'] = cal_score['total_score']
            
            logger.info(f"Calculated score for result ID {result.id}: {result.new_score}")
            result.save(update_fields=["new_score"])
    except Exception as e:
        logger.error(f"Error in ReEvaluation function: {str(e)}")
        return None
    return "Done"


def calculate_marks_general(result):
    """
    Calculates the total marks obtained for a given assessment result 
    that belongs to general levels such as: G1L1, G1L2, G2L1, G2L2, G3L1, G3L2, and CS.

    This function aggregates scores from all answer types in a single optimized pass.

    Parameters:
        result (Result): A Result instance containing related answers
    """
    logger.info("Inside calculate_marks_general function")
    try:
        # Fetch all answers with related data in a single optimized query
        all_answers = result.answers.select_related(
            'question',
            'selected_option',
            'fillup_question',
            'audio_question'
        ).all()
        
        if not all_answers.exists():
            logger.info(f"No answers found for result ID {result.id}")
            return {"total_score": 0}
        
        total_score = calculate_score_optimized(all_answers)
        logger.info(f"Total score calculated: {total_score} for result ID {result.id}")
        return {"total_score": total_score}
    except Exception as e:
        logger.error(f"Error in calculate_marks_general: {str(e)}")
        return {"total_score": 0}
    

def calculate_marks_lseqi(result):
    logger.info("Inside calculate_marks_lseqi function")
    """
    Calculates individual category scores for LS1EIQ1 assessments based on 
    the selected options for each question.

    LS1EIQ1 assessments are divided
    into five core categories:
        - SA: Self Awareness
        - ME: Managing Emotions
        - MO: Motivating Oneself
        - EP: Empathy
        - SS: Social Skill

    The function aggregates scores for each category by summing the values of 
    the `selected_option.option` field where the related question belongs to 
    the respective category.

    Parameters:
        result (Result): A Result instance whose related `Answer` objects are 
                         evaluated.
    """

    try:
        assessment_answer = result.answers.select_related("selected_option",
                                                          "question__category")
        marks = assessment_answer.aggregate(
            self_awareness=Sum(
                Case(
                    When(question__category="SA",
                         then=Cast("selected_option__option", IntegerField())),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            managing_emotions=Sum(
                Case(
                    When(question__category="ME",
                         then=Cast("selected_option__option", IntegerField())),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            motivating_oneself=Sum(
                Case(
                    When(question__category="MO",
                         then=Cast("selected_option__option", IntegerField())),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            empathy=Sum(
                Case(
                    When(question__category="EP",
                         then=Cast("selected_option__option", IntegerField())),
                    default=0,
                    output_field=IntegerField()
                )
            ),
            social_skill=Sum(
                Case(
                    When(question__category="SS",
                         then=Cast("selected_option__option", IntegerField())),
                    default=0,
                    output_field=IntegerField()
                )
            ),
        )
    except Exception as e:
        logger.error(f"Error in calculate_marks_lseqi: {str(e)}")
        marks = {
            "self_awareness": 0,
            "managing_emotions": 0,
            "motivating_oneself": 0,
            "empathy": 0,
            "social_skill": 0,
        }

    return marks


def calculate_marks_lsfs(result):
    """
     Calculates category-wise correct answer counts for LS1FS1 assessments.

    LS1FS1 assessments categorize questions into four parenting or emotional 
    response styles:
        - DM : Dismissing
        - DAP: Disapproving
        - LF : Laissez-Faire
        - EC : Emotion Coaching

    This function counts how many correct answers (`is_correct=True`) the 
    user has given under each category.

    Parameters:
        result (Result): A Result instance containing related `Answer` 
                         objects to be evaluated.
    """
    logger.info("Inside calculate_marks_lsfs function")
    try:
        counts = result.answers.all().aggregate(
            dismissing=Count(
                Case(
                    When(question__category="DM",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            disapproving=Count(
                Case(
                    When(question__category="DAP",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            laissez_faire=Count(
                Case(
                    When(question__category="LF",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            emotion_coaching=Count(
                Case(
                    When(question__category="EC",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
        )
    except Exception as e:
        logger.error(f"Error in calculate_marks_lsfs: {str(e)}")
        counts = {
            "dismissing": 0,
            "disapproving": 0,
            "laissez_faire": 0,
            "emotion_coaching": 0,
        }
    return counts


def calculate_marks_lsmo(result):
    """
    Calculates category-wise correct answer counts for LS1MO1 assessments.

    LS1MO1 assessments evaluate answers based on six specific moral orientation
    categories, where each question belongs to one of the following:
        - PmB
        - PmG
        - PvB
        - PvG
        - PsB
        - PsG

    This function counts how many correct answers (`is_correct=True`) the 
    user has provided in each category.

    Parameters:
        result (Result): A Result instance containing related `Answer` 
                         objects to be evaluated.
    """
    logger.info("Inside calculate_marks_lsmo function")
    try:
        counts = result.answers.all().aggregate(
            cal_pmb=Count(
                Case(
                    When(question__category="PmB",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            cal_pmg=Count(
                Case(
                    When(question__category="PmG",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            cal_pvb=Count(
                Case(
                    When(question__category="PvB",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            cal_pvg=Count(
                Case(
                    When(question__category="PvG",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            cal_psb=Count(
                Case(
                    When(question__category="PsB",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
            cal_psg=Count(
                Case(
                    When(question__category="PsG",
                         selected_option__is_correct=True, then=1),
                    output_field=IntegerField()
                )
            ),
        )

    except Exception as e:
        logger.error(f"Error in calculate_marks_lsmo: {str(e)}")
        counts = {
            "cal_pmb": 0,
            "cal_pmg": 0,
            "cal_pvb": 0,
            "cal_pvg": 0,
            "cal_psb": 0,
            "cal_psg": 0}
    return counts


def safe_division(numerator, denominator):
    try:
        denominator = int(denominator)
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def recalculate_answer(answer, send):
    """Recalculate the answer based on the instance and save it."""
    logger.info(f"Recalculating answer for {send}")
    try:
        if send == "Question":
            logger.info(f"Recalculating answers for Question")
            for ans in answer:
                logger.info(f"Processing text answer ID: {ans.id}")
                correct_answer = ans.question.correct_answer
                your_answer = ans.selected_option.option
                if correct_answer == your_answer:
                    ans.selected_option.is_correct = True
                else:
                    ans.selected_option.is_correct = False
                ans.selected_option.save(update_fields=["is_correct"])
                ans.save()
        elif send == "FillInTheBlank":
            logger.info(f"Recalculating answers for FillInTheBlank")
            for ans in answer:
                logger.info(f"Processing fill-in-the-blank answer ID: {ans.id}")
                ans.save()
        else:
            logger.info(f"Recalculating answers for AudioQuestion")
            for ans in answer:
                logger.info(f"Processing audio question answer ID: {ans.id}")
                ans.save()
    except Exception as e:
        logger.error(f"Error recalculating answer for {send}: {e}")

def calculate_score_optimized(all_answers):
    try:
        point = 0
        # 1. Score Multiple Choice (Standard Text Questions)
        text_questions = all_answers.filter(question__isnull=False)
        if text_questions.exists():
            point += text_questions.filter(selected_option__is_correct=True).count()

        # 2. Score Fill-in-the-blank (JSONB PostgreSQL Optimization)
        fillup_qs = all_answers.filter(
            question__isnull=True, 
            fillup_question__isnull=False
        ).select_related('fillup_question')

        if fillup_qs.exists():
            # Use the actual table names from your database. '
            matching_points_sql = """
                COALESCE((
                    SELECT count(*)
                    FROM jsonb_each_text(assessment_answer.fillup_answer) AS u
                    JOIN jsonb_each_text((
                        SELECT correct_answer
                        FROM assessment_fillintheblank
                        WHERE assessment_fillintheblank.id = assessment_answer.fillup_question_id
                    )) AS c
                    ON u.key = c.key AND TRIM(u.value)= TRIM(c.value)
                ), 0)
            """

            fillup_result = fillup_qs.annotate(
                row_points=RawSQL(matching_points_sql, [])
            ).aggregate(
                total_score=Sum('row_points')
            )

            point += (int(fillup_result['total_score']) or 0)

        # 3. Score Audio Questions
        audio_answers = all_answers.filter(audio_question__isnull=False)
        if audio_answers.exists():
            for answer in audio_answers:
                # Safely check if the method exists
                if hasattr(answer.audio_question, 'is_correct'):
                    score, _, _ = answer.audio_question.is_correct(answer.audio_answer)
                    point += score
            
        return point
    
    except Exception as e:
        logger.error(f"Error in calculate_score_optimized: {str(e)}")
        return 0