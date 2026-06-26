from django.db.models.signals import post_save,pre_save,post_delete
from django.dispatch import receiver
from .models import AssessmentResult, Category, Content, Disability, Option, Organization, Question, Assessment,FillInTheBlank,AudioQuestion,Answer
import logging
from assessment.services.calculator import ReEvaluation, recalculate_answer
from django.core.cache import cache
logger = logging.getLogger("django")

@receiver(post_save, sender=Organization)
@receiver(post_save, sender=Disability)
def clear_organisation_cache(sender, instance, **kwargs):
    """Helper to clear organization-related cache."""
    if sender == Organization:
        cache_key = "all_organizations_id_name"
        cache.delete(cache_key)
    elif sender == Disability:
        cache_key = "all_disabilities_id_name"
        cache.delete(cache_key)

@receiver(post_save, sender=Assessment)  # Handles create and update
@receiver(post_delete, sender=Assessment)  # Handles delete
def clear_assessment_cache(sender, instance, **kwargs):
    """
    Signal handler that clears the assessment list cache for the author when
    an Assessment is deleted/update/create.

    This ensures that users do not see stale data on their dashboard
    after removing an assessment.
    """
    try:
        if instance.author:
            cache_key = f"assessment_user_{instance.author.id}"
            cache.delete(cache_key)
            cache_key = f"assessment_with_prefetch_{instance.id}"
            cache.delete(cache_key)
            cache_key = f"assessment_{instance.id}"
            cache.delete(cache_key)
            

            # Determine signal type
            signal_type = 'Deleted' if kwargs.get('signal') == post_delete else (
                'Created' if kwargs.get('created', False) else 'Updated'
            )

            logger.info(
                f"Assessment {signal_type} - Cache key '{cache_key}' cleared for user {instance.author.id}"
            )
    except Exception as e:
        logger.error(f"Error clear  AssessmentResult cache : {e}")

# @receiver(post_save, sender=AssessmentResult)  # Handles create and update
# @receiver(post_delete, sender=AssessmentResult)  # Handles delete
# def clear_assessment_result_cache(sender, instance, **kwargs):
#     """
#      Signal handler that clears the assessment result cache for the user when
#     an AssessmentResult is created/updated/delete.

#     This ensures that the cache reflects the latest result data.
#     """
#     try:
#         if instance.assessment and instance.assessment.author:
#             # logger.info(f"here {instance.assessment.values()}")
#             cache_key = f"assessment_results_user_{instance.assessment.author.id}_assessment_{instance.assessment.id}"
#             cache.delete(cache_key)
#             # Determine signal type
#             signal_type = 'Deleted' if kwargs.get('signal') == post_delete else (
#                 'Created' if kwargs.get('created', False) else 'Updated'
#             )

#             logger.info(
#                 f"AssessmentResult {signal_type} - Cache key '{cache_key}' cleared for user {instance.assessment.author.id}"
#             )
#     except Exception as e:
#         logger.error(f"Error clear  AssessmentResult cache : {e}")

# @receiver(post_save, sender=AssessmentResult)
# def set_score_based_on_level(sender, instance, created, **kwargs):
#     '''
#     Signal to set the score for an AssessmentResult based on the assessment
#     level.
#     This function is triggered after an AssessmentResult is saved.
#     '''
#     logger.info(f"Post-save signal triggered for AssessmentResult ID {instance.id}, created: {created}")
#     if created:
#         logger.info(f"Creating score for new AssessmentResult: {instance.id}")
#         try:
#             if instance.assessment and instance.assessment.level in ['LS1EIQ1', 'LS1MO1', 'LS1FS1']:
#                 categories = Category.getLevelCategory(level=instance.assessment.level)
#                 instance.new_score = {category["name"]: 0 for category in categories}
#             else:
#                 instance.new_score = {"total_score": 0}
#             instance.save(update_fields=["new_score"]) 
#         except Exception as e:
#             logger.error(f"Error setting score for AssessmentResult {instance.id}: {e}")
#             instance.new_score = {"error": str(e)}
#             instance.save(update_fields=["new_score"])

def get_old_instance_data(model_class, instance_id, fields):
    """Helper to retrieve old instance data safely."""
    try:
        old_instance = model_class.objects.get(pk=instance_id)
        data = {}
        for key in fields:
            if "__" in key:
                rel, rel_field = key.split("__", 1)
                rel_obj = getattr(old_instance, rel, None)
                data[key] = getattr(rel_obj, rel_field, None) if rel_obj else None
            else:
                data[key] = getattr(old_instance, key, None)
        return data
    except model_class.DoesNotExist:
        return {field: None for field in fields}

@receiver(pre_save, sender=Question)
@receiver(pre_save, sender=FillInTheBlank)
@receiver(pre_save, sender=AudioQuestion)
@receiver(pre_save, sender=Option)
@receiver(pre_save, sender=Content)
def cache_old_values(sender, instance, **kwargs):
    """Cache old values before saving to detect changes later."""
    try:
        logger.info(f"Pre-save signal triggered for {sender.__name__} ID {instance.id}")
        if not instance.pk:
            return

        field_map = {
            Question: ("question",),
            FillInTheBlank: ("correct_answer", "sentence"),
            AudioQuestion: ("answer", "question"),
            Option: ("option",),
            Content: ("content",),
        }

        fields = field_map.get(sender, ())
        old_data = get_old_instance_data(sender, instance.pk, fields)

        for key, value in old_data.items():
            setattr(instance, f"_old_{key}", value)
            logger.info(f"Cached old value for {sender.__name__} ID {instance.id}: _old_{key} = {value}")
    except Exception as e:
        logger.error(f"Error caching old values for {sender.__name__} ID {instance.id}: {e}")


def get_related_assessments(sender, instance):
    """Return queryset of related assessments based on sender type."""
    if sender == Question:
        return Assessment.objects.filter(questions=instance)
    elif sender == FillInTheBlank:
        return Assessment.objects.filter(fillup_questions=instance)
    elif sender == AudioQuestion:
        return Assessment.objects.filter(audio_questions=instance)
    elif sender == Option:
        return Assessment.objects.filter(questions__options=instance)
    elif sender == Content:
        return Assessment.objects.filter(questions__content=instance)
    return Assessment.objects.none()


def get_related_answer(sender, instance):
    """Return the related answer based on sender type."""
    if sender == Question:
        return Answer.objects.filter(question=instance)
    elif sender == FillInTheBlank:
        return Answer.objects.filter(fillup_question=instance)
    elif sender == AudioQuestion:
        return Answer.objects.filter(audio_question=instance)
    return None

@receiver(post_save, sender=Question)
@receiver(post_save, sender=FillInTheBlank)
@receiver(post_save, sender=AudioQuestion)
@receiver(post_save, sender=Option)
@receiver(post_save, sender=Content)
def handle_changes(sender, instance, **kwargs):
    """Trigger re-evaluation if relevant fields are changed."""
    logger.info(f"Post-save signal triggered for {sender.__name__} ID {instance.id}")
    try:
        fields_to_check = {
            Question: ["question"],
            FillInTheBlank: ["correct_answer","sentence"],
            AudioQuestion: ["answer","question"],
            Option: ["option"],
            Content: ["content"],
        }

        changed = False
        for field in fields_to_check.get(sender, []):
            if "__" in field:
                rel, rel_field = field.split("__", 1)
                rel_obj = getattr(instance, rel, None)
                old_value = getattr(rel_obj, rel_field, None) if rel_obj else None
                new_value = getattr(getattr(instance, rel, None), rel_field, None) if getattr(instance, rel, None) else None
            else:
                old_value = getattr(instance, f"_old_{field}", None)
                new_value = getattr(instance, field, None)
            logger.info(f"Checking field '{field}': old value='{old_value}', new value='{new_value}'")
            if old_value != new_value:
                logger.info(f"{sender.__name__} ID {instance.id} field '{field}' changed from '{old_value}' to '{new_value}'")
                changed = True

        if changed:
            # # Get related answer 
            # answer = get_related_answer(sender, instance)
            # if answer.exists():
            #     # If related answer exists, we can perform actions on it
            #     logger.info(f"Related answer found for {sender.__name__} ID {instance.id}: {answer}")
            #     if sender == Question:
            #         if instance.level not in ['LS1EIQ1']:
            #             recalculate_answer(answer, instance, send=sender.__name__)
            #     else:
            #         recalculate_answer(answer, instance, send=sender.__name__)
            assessments = get_related_assessments(sender, instance)
            logger.info(f" assessment are {assessments}")
            if assessments.exists():
                for assessment in assessments:
                    logger.info(f"Related assessment found for {sender.__name__} ID {instance.id}: {assessment.id}")
                    cache_key = f"assessment_with_prefetch_{assessment.id}"
                    cache.delete(cache_key)
                    cache_key = f"assessment_{assessment.id}"
                    cache.delete(cache_key)
                    cache_key = f"assessment_question_{instance.id}"
                    cache.delete(cache_key)
                # assessment_type = assessments.first().level
                # results = AssessmentResult.objects.filter(assessment__in=assessments)
                # if results.exists():
                #     logger.info(f"Re-evaluating due to changes for {sender.__name__} ID {instance.id}")
                #     ReEvaluation(results, assessment_type)
    except Exception as e:
        logger.error(f"Error handling changes for {sender.__name__} ID {instance.id}: {e}")
