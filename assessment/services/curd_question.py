from assessment.models import FillInTheBlank, Question, AudioQuestion, Category, Option
import random
import json
import logging
logger = logging.getLogger('django')


def delete_question(original_question, upcoming_question):
    try:
        for question in original_question:
            if str(question.id) not in upcoming_question:
                logger.info(f"Deleting question with id: {question.id} where upcoming_question is {upcoming_question} and str(question.id) is {str(question.id)}")
                question.delete()
                original_question = original_question.exclude(id=question.id)
    except Exception as e:
        logger.error(f"Error occurred while deleting questions. Original questions: {original_question}, Upcoming questions: {upcoming_question}. Exception: {e}")
    return original_question


def create_row_fillup_question(user, id, list_upcoming_fillup_question,
                               user_fillup_question_qs, blanks_list,
                               fillup_question_ids, fillup_ids,
                               content_level, content_subLevel,
                               content_subject, user_content_qs):
    """
    Creates or updates fill-in-the-blank questions for a user based on the
    provided upcoming questions and associated metadata.

    This function iterates over the list of upcoming fill-in-the-blank questions
    and either updates an existing question or creates a new one, depending on 
    whether the question ID exists in the provided list.

    Parameters:
        user (User): The user creating or updating the questions.
        id (int): If id is provided, fetch the content and related questions.
                  If id is not provided, initialize empty content and questions.
        list_upcoming_fillup_question (list): A list of tuples where each tuple
            contains a type (in which case having fill-in-the-blank) and
            the sentence text.
        user_fillup_question_qs (QuerySet): QuerySet of existing FillInTheBlank
            questions related to the user.
        blanks_list (list): A list of 10 sublists, each containing blank values
            for each question (Blank1 to Blank10).
        fillup_question_ids (list): List of IDs corresponding to existing
            fill-in-the-blank questions.
        fillup_ids (list): List of current(upcoming) fillup IDs aligned with `list_upcoming_fillup_question`.
        content_level (str): The level of the content (e.g., G1, G2, etc.).
        content_subLevel (str): The sub-level within the content level.
        content_subject (str): The subject associated with the question (e.g., English).
        user_content_qs (QuerySet): Content object to which the question will be attached.

    Returns:
        None

    Side Effects:
        - Updates existing FillInTheBlank instances if matched by ID.
        - Creates new FillInTheBlank instances if no match is found.
        - Populates the `correct_answer` field using provided blanks.
        - Saves each updated or newly created instance to the database.
    """
    try:
        for index, fillup_question in enumerate(list_upcoming_fillup_question):
            if fillup_question[1]:
                typ, fillup_text = fillup_question
                fillup_text = fillup_text.strip().replace("`", "\`")
                if id and str(fillup_ids[index]) in map(str, fillup_question_ids):
                    fillup = user_fillup_question_qs[index]
                    if fillup_text != fillup.sentence:
                        fillup.sentence = fillup_text
                        fillup.save(update_fields=["sentence"])
                else:
                    fillup = FillInTheBlank.create(
                        sentence=fillup_text,
                        level=content_level,
                        sub_level=content_subLevel,
                        subject=content_subject,
                        content=user_content_qs,
                        author=user,
                    ) 
                blank_text = [blanks_list[0][index],
                              blanks_list[1][index],
                              blanks_list[2][index],
                              blanks_list[3][index],
                              blanks_list[4][index],]
                try:
                    # create dictionary of blank for saving in correct answer 
                    blanks_dict = {f"Blank{ind+1}": blank.strip() for ind, blank in enumerate(blank_text) if blank}
                    if fillup.correct_answer != blanks_dict:
                        fillup.correct_answer = blanks_dict
                        fillup.save(update_fields=["correct_answer"])
                except Exception as e:
                    logger.error(f"Error while saving fillup question: {e}")
                    fillup.correct_answer = {}
                    fillup.save(update_fields=["correct_answer"])
                
    except Exception as e:
        logger.error(f"Error occurred while creating fillup question: {e}")
        

def create_row_audio_question(user, id,
                              list_upcoming_audio_question,
                              user_audio_question_qs,
                              audio_question_id_list,
                              content_level, content_subLevel,
                              content_subject, user_content_qs,
                              audio_answer_list):
    """
    Creates or updates audio-based assessment questions for a user based on
    provided question data and metadata.

    This function processes a list of upcoming audio questions and:
    - Updates existing `AudioQuestion` instances if the ID is provided and the
      question type is not marked as 'new'.
    - Creates new `AudioQuestion` instances otherwise.
    - Sets or updates fields such as question audio text, level, sub-level,
      subject, associated content, and the correct answer.

    Parameters:
        user (User): The user who is creating or updating the questions.
        id (int): If id is provided, fetch the content and related questions.
                  If id is not provided, initialize empty content and questions.
        list_upcoming_audio_question (list): A list of tuples with type information 
            and the question audio text.
        user_audio_question_qs (QuerySet): Existing audio questions that may be updated.
        audio_question_id_list (list): List of IDs of audio questions.
        content_level (str): The level of the content (e.g., G1, G2).
        content_subLevel (str): The sub-level of the educational content (e.g., L1, L2).
        content_subject (str): The subject of the question (e.g., English).
        user_content_qs (QuerySet): The content object to which the question is attached.
        audio_answer_list (list): List of corresponding correct answers for the questions.

    Returns:
        None

    Side Effects:
        - Updates or creates `AudioQuestion` objects and saves them to the database.
    """
    try:
        for index, audio_question in enumerate(list_upcoming_audio_question):
            if audio_question:
                typ, question_audio = audio_question
                if id and 'new' not in typ:
                    audio = user_audio_question_qs[index]
                    if question_audio != audio.question:
                        audio.question = question_audio
                        audio.save(update_fields=["question"])
                else:
                    audio = AudioQuestion.create(
                        question=question_audio,
                        level=content_level,
                        sub_level=content_subLevel,
                        subject=content_subject,
                        content=user_content_qs,
                        author=user,
                    )
                audio_answer = audio_answer_list[index].strip()
                if audio.answer != audio_answer:
                    audio.answer = audio_answer
                    audio.save(update_fields=["answer"])
    except Exception as e:
        logger.error(f"Error occurred while creating audio question: {e}")


def create_row_text_question(user, id,
                             list_upcoming_question,
                             user_question_qs, question_ids_changes,
                             question_ids, option1_list, option2_list,
                             option3_list, option4_list, option5_list,
                             content_level, content_subLevel,
                             content_subject,
                             user_content_qs, correct_option_list,
                             levels_with_multiple_categories,
                             custom_calculation_levels, categorie_list):
    """
    Creates or updates text-based multiple-choice questions for a user.

    This function processes a list of upcoming text questions and handles:
    - Updating existing `Question` objects if an ID match is found.
    - Creating new `Question` instances otherwise.
    - Setting metadata such as level, sub-level, subject, and content reference.
    - Managing the options (1 to 5) associated with each question, including creation,
      update, or deletion based on the provided input.
    - Setting the correct answer if the question is not part of a custom calculation level.
    - Assigning a category if the level supports multiple categories.

    Parameters:
        user (User): The user who is creating or updating the questions.
        id (int): If id is provided, fetch the content and related questions.
                  If id is not provided, initialize empty content and questions.
        list_upcoming_question (list): A list of tuples (type, question_text).
        user_question_qs (QuerySet): Existing user-created questions to update.
        question_ids_changes (list): List of question IDs used for update comparison.
        question_ids (list): IDs of questions passed from the client.
        option1_list to option5_list (list): Lists of option texts.
        content_level (str):  The level of the content (e.g., G1, G2).
        content_subLevel (str): Sub-level (e.g., L1, L2).
        content_subject (str): Subject of the question (e.g., English).
        user_content_qs (QuerySet): Content object the question belongs to.
        correct_option_list (list): List indicating which option is correct per question.
        levels_with_multiple_categories (list): Levels that support category assignment.
        custom_calculation_levels (list): Levels where correct option marking is skipped.
        categorie_list (list): List of categories to assign based on index.

    Returns:
        None

    Side Effects:
        - Creates or updates `Question` and related `Option` instances in the database.
        - Logs errors to the application logger if encountered.
    """
    try:
        for index, ques in enumerate(list_upcoming_question):
            if ques[1]:
                typ, question_text = ques
                question_text = question_text.strip().replace("`", "\`")
                if id and str(question_ids_changes[index]) in map(str, question_ids):
                    question = user_question_qs[index]
                    if question_text != question.question:
                        question.question = question_text
                        question.save(update_fields=["question"])

                else:
                    question = Question.create(
                        question=question_text,
                        level=content_level,
                        sub_level=content_subLevel,
                        subject=content_subject,
                        content=user_content_qs,
                        author=user,
                    )
                """
                saving question category when the level include in
                levels_with_multiple_categories
                """
                if (question.level in levels_with_multiple_categories) and categorie_list[index] and question.category != categorie_list[index]:
                    question.category = categorie_list[index]
                    question.save(update_fields=["category"])


                option_text = [option1_list[index], option2_list[index],
                               option3_list[index], option4_list[index],
                               option5_list[index]]
                option_texts = [o.strip().replace("`", "\`") for o in option_text if o]

                existing_options  = list(question.options.all().order_by("id"))
                try:
                    # 1) Same count → update values only if changed
                    if len(existing_options) == len(option_texts):
                        for ind, opt in enumerate(existing_options):
                            new_val = option_texts[ind]
                            update_fields = []
                            if opt.option != new_val:
                                opt.option = new_val
                                update_fields.append("option")
                            if question.level not in custom_calculation_levels:
                                new_correct = correct_option_list[index] == str(ind + 1)
                                if opt.is_correct != new_correct:
                                    opt.is_correct = new_correct
                                    update_fields.append("is_correct")
                            if update_fields:
                                opt.save(update_fields=update_fields)

                    # 2) More new options → update existing + create new
                    elif len(existing_options) < len(option_texts):
                        for ind, new_val in enumerate(option_texts):
                            if ind < len(existing_options):
                                opt = existing_options[ind]
                                update_fields = []
                                if opt.option != new_val:
                                    opt.option = new_val
                                    update_fields.append("option")
                                if question.level not in custom_calculation_levels:
                                    new_correct = correct_option_list[index] == str(ind + 1)
                                    if opt.is_correct != new_correct:
                                        opt.is_correct = new_correct
                                        update_fields.append("is_correct")
                                if update_fields:
                                    opt.save(update_fields=update_fields)
                            else:
                                new_opt = Option.objects.create(option=new_val)
                                if question.level not in custom_calculation_levels:
                                    new_opt.is_correct = correct_option_list[index] == str(ind + 1)
                                    new_opt.save(update_fields=["is_correct"])
                                question.options.add(new_opt)

                    # 3) Fewer new options → update remaining, delete extras
                    else:
                        for ind, opt in enumerate(existing_options):
                            if ind < len(option_texts):
                                new_val = option_texts[ind]
                                update_fields = []
                                if opt.option != new_val:
                                    opt.option = new_val
                                    update_fields.append("option")
                                if question.level not in custom_calculation_levels:
                                    new_correct = correct_option_list[index] == str(ind + 1)
                                    if opt.is_correct != new_correct:
                                        opt.is_correct = new_correct
                                        update_fields.append("is_correct")
                                if update_fields:
                                    opt.save(update_fields=update_fields)
                            else:
                                opt.delete()
                except Exception as e:
                    logger.error(f"Error while saving question options: {e}")
    except Exception as e:
        logger.error(f"Error occurred while creating text question: {e}")


def _select_random_by_content(queryset, requested_count, min_per_content=3, max_per_content=4):
    """
    Select questions randomly while preferring content-grouped selection.
    The selector aims to keep each chosen content block between min/max items.
    Falls back to any random items if strict grouping cannot satisfy the request.
    """
    # Normalize and short-circuit invalid counts early.
    requested_count = int(requested_count or 0)
    if requested_count <= 0:
        return []

    # Pull candidates once; selection happens in memory after this point.
    candidates = list(queryset.select_related("content"))
    if len(candidates) < requested_count:
        return []

    # Group by content so selected questions remain context-clustered.
    by_content = {}
    for item in candidates:
        by_content.setdefault(item.content_id, []).append(item)

    content_ids = list(by_content.keys())
    random.shuffle(content_ids)

    selected = []
    selected_ids = set()
    remaining = requested_count

    for content_id in content_ids:
        if remaining <= 0:
            break

        content_items = by_content[content_id][:]
        random.shuffle(content_items)

        # Prefer a chunk of 3-4 per content when possible.
        chunk_limit = min(max_per_content, len(content_items), remaining)
        if chunk_limit <= 0:
            continue

        if chunk_limit >= min_per_content:
            # Normal path: pick 3-4 from a content block.
            chunk_size = random.randint(min_per_content, chunk_limit)
        else:
            # Take smaller chunk only when unavoidable (final fill / sparse content).
            chunk_size = chunk_limit

        picked = content_items[:chunk_size]
        selected.extend(picked)
        selected_ids.update(item.id for item in picked)
        remaining -= len(picked)

    # If grouped picks are not enough, top up from the remaining pool.
    if remaining > 0:
        leftovers = [item for item in candidates if item.id not in selected_ids]
        random.shuffle(leftovers)
        selected.extend(leftovers[:remaining])

    return selected if len(selected) == requested_count else []


def _parse_sublevel_distribution(raw_distribution):
    """
    Parse JSON payload from generate-assessment form:
    {
      "text": {"General": 2, "Noun": 3},
      "audio": {"General": 1},
      "fillup": {"Noun": 2}
    }
    """
    # Empty payload means no distribution mapping was provided.
    if not raw_distribution:
        return {"text": {}, "audio": {}, "fillup": {}}

    # Ignore malformed JSON and fall back to empty structure.
    try:
        payload = json.loads(raw_distribution)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"text": {}, "audio": {}, "fillup": {}}

    # Keep only positive integer counts for known sections.
    normalized = {"text": {}, "audio": {}, "fillup": {}}
    for section in normalized.keys():
        section_data = payload.get(section, {})
        if not isinstance(section_data, dict):
            continue
        for sub_level, count in section_data.items():
            try:
                count_int = int(count)
            except (TypeError, ValueError):
                continue
            if count_int > 0:
                normalized[section][sub_level] = count_int
    return normalized


def _select_for_type(
    queryset,
    requested_count,
    distribution_key,
    label,
    has_sublevels,
    sublevel_distribution,
    allowed_sublevels,
    filter_dict,
):
    # No questions requested for this type.
    requested_count = int(requested_count or 0)
    if requested_count <= 0:
        return [], None, set()

    # For EN/COM-style flows, select per sub-level based on distribution.
    if has_sublevels:
        distribution = sublevel_distribution.get(distribution_key, {})
        if not distribution:
            return None, f"Please define {label} counts for sublevels.", set()
        if sum(distribution.values()) != requested_count:
            return (
                None,
                f"{label.capitalize()} total must match requested count ({requested_count}).",
                set(),
            )

        picked_items = []
        used_sublevels = set()
        for sub, count in distribution.items():
            if sub not in allowed_sublevels:
                return None, f"Invalid sublevel '{sub}' for {label}.", set()
            scoped_filter = {**filter_dict, "sub_level": sub}
            picked = _select_random_by_content(queryset.filter(**scoped_filter), count)
            if len(picked) != count:
                return None, f"Not enough {label} for sublevel {sub}.", set()
            used_sublevels.add(sub)
            picked_items.extend(picked)
        return picked_items, None, used_sublevels

    # For single-sublevel or no-sublevel flows, use content-aware random selection.
    picked = _select_random_by_content(queryset.filter(**filter_dict), requested_count)
    if len(picked) != requested_count:
        return (
            None,
            f"Unable to generate {label} with current constraints. "
            "Try reducing count or adding more questions.",
            set(),
        )
    return picked, None, set()


def _safe_int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0