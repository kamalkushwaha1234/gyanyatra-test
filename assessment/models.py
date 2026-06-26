import uuid
from django.db import models
from django.utils import timezone
from assessmentPrishni.settings import DOMAIN
from django.template.defaultfilters import slugify
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
import logging
from django.db.models import Count,Prefetch
from django.core.exceptions import ValidationError
from django.db.models import Count, Value, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from simple_history.models import HistoricalRecords
from django.core.cache import cache

"""
Add HistoricalRecords to track model changes

- Integrated `HistoricalRecords` from the `django-simple-history` package into models like `Question`, `FillInTheBlank`, `AudioQuestion`, `Assessment`, and others.
- Purpose: To maintain a history of changes made to these models, including create, update, and delete operations.
- This allows us to track changes over time, audit modifications, and restore previous states if necessary.
- Useful for debugging, compliance, and maintaining data integrity in the application.

Note:  Excluded the `Option` model from history tracking as it is already tracked via raw SQL triggers.
"""

logger = logging.getLogger('django')

GRADES = [
    ("A1", "A1"),
    ("A2", "A2"),
    ("B1", "B1"),
    ("B2", "B2"),
    ("C1", "C1"),
    ("C2", "C2"),
]

StatusChoices = [
    ("pending", "Pending"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]

ASSESSMENT_LEVELS = [
    ["G1L1", "Group 1 Level 1"],
    ["G1L2", "Group 1 Level 2"],
    ["G1L3", "Group 1 Level 3"],
    ["GReflexL1", "Group Reflexology Level 1"],
    ["GSlL1", "Group Sutherland Level 1"],
    ["G2L1", "Group 2 Level 1"],
    ["G2L2", "Group 2 Level 2"],
    ["G2L3", "Group 2 Level 3"],
    ["G3L1", "Group 3 Level 1"],
    ["G3L2", "Group 3 Level 2"],
    ["G3L3", "Group 3 Level 3"],
    ["LS1EIQ1", "Life Skills 1 EQ 1"],
    ["LS1MO1", "Life Skills 1 MO 1"],
    ["LS1FS1", "Life Skills 1 FS 1"],
    ["CS", "Cold Storage"],
]
SUB_LEVELS = [
    ["General", "General"],
    ["Noun", "Noun"],
    ["Pronoun", "Pronoun"],
    ["Adjective", "Adjective"],
    ["Preposition", "Preposition"],
    ["Adverb", "Adverb"],
    ["Verb", "Verb"],
    ["Conjunct", "Conjunction"],
    ["Interject", "Interjection"],
    ["Sentences", "Types of Sentences"],
    ["ReadComp", "Reading Comprehension"],
    ["WriteComp", "Writing Comprehension"],
    ["SpeakConv", "Speaking Conversations"],
    ["Listening", "Listening Skills"],
    ["Tenses", "Tenses"],
    ["AntSyn", "Antonyms & Synonyms"],
    ["Contract", "Contractions"],
    ["OfficeCorr", "Office Correspondence"],
    ["Phonics", "Phonics"],
    ["BasicCon", "Basic Concepts"],
    ["Array", "Arrays"],
    ["LinkedList", "LinkedList"],
    ["Stack", "Stack"],
    ["Queue", "Queue"],
    ["Searching", "Searching"],
    ["Sorting", "Sorting"],
    ["Mixed", "Mixed"],

]

MAP_SUBLEVELS_TO_SUBJECT = {
    "EN": [
        ["General", "General"],
        ["Noun", "Noun"],
        ["Pronoun", "Pronoun"],
        ["Adjective", "Adjective"],
        ["Preposition", "Preposition"],
        ["Adverb", "Adverb"],
        ["Verb", "Verb"],
        ["Conjunct", "Conjunction"],
        ["Interject", "Interjection"],
        ["Sentences", "Types of Sentences"],
        ["ReadComp", "Reading Comprehension"],
        ["WriteComp", "Writing Comprehension"],
        ["SpeakConv", "Speaking Conversations"],
        ["Listening", "Listening Skills"],
        ["Tenses", "Tenses"],
        ["AntSyn", "Antonyms & Synonyms"],
        ["Contract", "Contractions"],
        ["OfficeCorr", "Office Correspondence"],
        ["Phonics", "Phonics"],
    ],
    "COM": [
        ["General", "General"],
        ["BasicCon", "Basic Concepts"],
        ["Array", "Arrays"],
        ["LinkedList", "LinkedList"],
        ["Stack", "Stack"],
        ["Queue", "Queue"],
        ["Searching", "Searching"],
        ["Sorting", "Sorting"],
    ],
}

SUBJECTS_HAVING_SUBLEVELS = ['English','Computer']

class Category(models.TextChoices):
    SELF_AWARENESS = 'SA', 'Self awareness'
    EMPATHY = 'EP', 'Empathy'
    MANAGING_EMOTIONS = 'ME', 'Managing emotions'
    MOTIVATING_ONESELF = 'MO', 'Motivating oneself'
    SOCIAL_SKILL = 'SS', 'Social Skill'
    DISMISSING = 'DM', 'Dismissing'
    DISAPPROVING = 'DAP', 'Disapproving'
    LAISSEZ_FAIRE = 'LF', 'Laissez Faire'
    EMOTION_COACHING = 'EC', 'Emotion Coaching'
    PMB = 'PmB', 'PmB'
    PMG = 'PmG', 'PmG'
    PVB = 'PvB', 'PvB'
    PVG = 'PvG', 'PvG'
    PSB = 'PsB', 'PsB'
    PSG = 'PsG', 'PsG'

    @classmethod
    def getCategoryWithLevel(cls):
        result = []
        for level, categories in MAP_CATEGORY_TO_LEVEL.items():
            for cat in categories:
                result.append({
                    "name": cat,
                    "label": cls(cat).label,
                    "level": level
                })
        return result

    @classmethod
    def getLevelCategory(cls, level):
        categories = MAP_CATEGORY_TO_LEVEL.get(level, [])
        result = []
        for cat in categories:
            result.append({
                "name": cat,
            })
        return result


MAP_CATEGORY_TO_LEVEL = {
    "LS1EIQ1": [Category.SELF_AWARENESS.value, Category.EMPATHY.value,
                Category.MANAGING_EMOTIONS.value, Category.MOTIVATING_ONESELF.value,
                Category.SOCIAL_SKILL.value],
    "LS1FS1": [Category.DISMISSING.value, Category.DISAPPROVING.value,
               Category.LAISSEZ_FAIRE.value, Category.EMOTION_COACHING.value],
    "LS1MO1": [Category.PMB.value, Category.PMG.value, Category.PVB.value,
               Category.PVG.value, Category.PSB.value, Category.PSG.value]
}


class Subject(models.TextChoices):
    ENGLISH = "EN", "English"
    LIFE_SKILL = "LS", "Life Skill"
    COMPUTER = "COM", "Computer"

    @classmethod
    def getSubjectDict(cls):
        subject_dict = []
        for sub in cls:
            subject_dict.append({
                "value": sub.value,
                "label": sub.label,
            })
        return subject_dict

    @classmethod
    def getlabel(cls,value):
        return cls(value).label


class UserManager(BaseUserManager):

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=255, blank=False)
    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)
    is_staff = models.BooleanField("staff status", default=False)
    is_active = models.BooleanField("active", default=True)
    is_superuser = models.BooleanField("superuser", default=False)
    is_creator = models.BooleanField("Creator", default=False)
    date_joined = models.DateTimeField(
        "date joined", default=timezone.now
    )

    USERNAME_FIELD = "email"
    objects = UserManager()

    def __str__(self):
        return self.email

    def full_name(self):
        return self.first_name + " " + self.last_name


class Content(models.Model):
    content = models.TextField()

    def __str__(self):
        return self.content if len(self.content) < 25 else self.content[:25] + "..."



class Option(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    option = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Generate a new UUID if it's not set
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.option if len(self.option) < 25 else self.option[:25] + "..."


class Question(models.Model):
    question = models.TextField()
    category = models.CharField(
        max_length=20, choices=Category.choices, null=True, blank=True
    )
    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="question_content"
    )
    options = models.ManyToManyField(Option, related_name="question_options")
    level = models.CharField(
        max_length=20, choices=ASSESSMENT_LEVELS, default=ASSESSMENT_LEVELS[0][0]
    )
    sub_level = models.CharField(
        max_length=40, choices=SUB_LEVELS, default=SUB_LEVELS[0][0], blank=True, null=True
    )
    subject = models.CharField(
        max_length=20,
        choices=Subject.choices,
        null=True,
        blank=True,
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="question")
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.question[:25]}..." if len(self.question) > 25 else self.question

    @classmethod
    def create(cls, question, content, level, sub_level, subject, author):
        try:
            question = cls(
                question=question,
                content=content,
                level=level,
                sub_level=sub_level,
                subject=subject,
                author=author
            )
            question.save()
        except Exception as e:
            logger.error(f"Error creating question: {e}")
            question = None
        return question

    @property
    def correct_answer(self):
        return self.options.filter(is_correct=True).first()
    
    def delete(self, *args, **kwargs):
        self.options.all().delete()
        super().delete(*args, **kwargs)

class FillInTheBlank(models.Model):
    sentence = models.TextField()
    def default_correct_answer():
        return {}
    correct_answer= models.JSONField(default=default_correct_answer)
    category = models.CharField(
        max_length=20, choices=Category.choices, null=True, blank=True
    )
    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="fillup_content"
    )
    level = models.CharField(
        max_length=20, choices=ASSESSMENT_LEVELS, default=ASSESSMENT_LEVELS[0][0]
    )
    sub_level = models.CharField(
        max_length=40, choices=SUB_LEVELS, default=SUB_LEVELS[0][0], blank=True, null=True
    )
    subject = models.CharField(
        max_length=20,
        choices=Subject.choices,
        null=True,
        blank=True,
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="fillup_author")
    history = HistoricalRecords()
    
    @classmethod
    def create(cls, sentence, content, level, sub_level, subject, author,
               blanks={}):
        try:
            # Create a dictionary for the blanks
            blanks_dict = {f"Blank{ind+1}": blank for ind, blank in enumerate(blanks) if blank}
            fillup = cls(
                sentence=sentence,
                content=content,
                level=level,
                sub_level=sub_level,
                subject=subject,
                author=author,
                correct_answer=blanks_dict,
            )
            fillup.save()
        except Exception as e:
            logger.error(f"Error creating fill-in-the-blank question: {e}")
            fillup = None
        return fillup

    @property
    def maximum_marks(self):
        return len(self.correct_answer)

class AudioQuestion(models.Model):
    question  = models.FileField(upload_to='audio_questions')
    content = models.ForeignKey(
        Content, on_delete=models.CASCADE, related_name="audio_question"
    )
    answer = models.CharField(max_length=255, blank=False, null=False)
    level = models.CharField(
        max_length=20, choices=ASSESSMENT_LEVELS, default=ASSESSMENT_LEVELS[0][0]
    )
    sub_level = models.CharField(
        max_length=40, choices=SUB_LEVELS, default=SUB_LEVELS[0][0], blank=True, null=True
    )
    subject = models.CharField(
        max_length=20,
        choices=Subject.choices,
        null=True,
        blank=True,
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="audio_question")
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.answer[:10]}..." if len(self.answer) > 10 else self.answer
  
    @classmethod
    def create(cls, question,  content, level, sub_level,
               subject, author, answer=''):
        try:
            audio_question = cls(
                question=question,
                answer=answer,
                content=content,
                level=level,
                sub_level=sub_level,
                subject=subject,
                author=author
            )
            audio_question.save()
        except Exception as e:
            logger.error(f"Error creating audio question: {e}")
            audio_question = None
        return audio_question

    def is_correct(self,response):
        response = response.split()
        answer = self.answer.split()
        count = 0
        verdicts = {}

        for index,word in enumerate(answer):
            if index < len(response):
                if word == response[index]:
                    count+=1
                    verdicts[word] = True
                else:
                    verdicts[word] = False
            else:
                verdicts[word] = False
        return count,verdicts,bool(count > 0)
    @property
    def maximum_marks(self):
        return len(self.answer.split())

class AssessmentManager(models.Manager):
    def get_with_prefetch(self, **filters):
        if "id" in filters:
            cache_key = f"assessment_with_prefetch_{filters['id']}"
        else:
            cache_key = f"assessment_with_prefetch_{'_'.join([f'{k}:{v}' for k,v in filters.items()])}"

        assessment = cache.get(cache_key)
        if not assessment:
            assessment = (
                self.get_queryset()
                .prefetch_related(
                    Prefetch(
                        "questions",
                        queryset=Question.objects.prefetch_related("options", "content")
                    ),
                    Prefetch(
                        "audio_questions",
                        queryset=AudioQuestion.objects.select_related("content")
                    ),
                    Prefetch(
                        "fillup_questions",
                        queryset=FillInTheBlank.objects.select_related("content")
                    )
                )
                .get(**filters)
            )

        cache.set(cache_key, assessment, timeout=3600)
        return assessment

    def with_metrics(self, user, include_total_questions=False,
                     include_get_user=False):
        queryset = self.get_queryset().filter(author=user).prefetch_related(
            "questions", "audio_questions", "fillup_questions")

        queryset = queryset.annotate(
            question_count=Count("questions",distinct=True),
            audio_count=Count("audio_questions",distinct=True),
            fillup_count=Count("fillup_questions",distinct=True),
        )

        if include_total_questions:
            queryset = queryset.annotate(
                totalquestions=F("question_count") +
                F("audio_count") + F("fillup_count")
            )

        if include_get_user:
            assessment_result_count_subquery = Subquery(
                AssessmentResult.objects.filter(assessment=OuterRef("pk"))
                .values("assessment")
                .annotate(count=Count("id"))
                .values("count")[:1]
            )
            queryset = queryset.annotate(
                getuser=Coalesce(assessment_result_count_subquery, Value(0))
            )
        return queryset.order_by("-id")

class Assessment(models.Model):
    name = models.CharField(max_length=255)
    questions = models.ManyToManyField(Question, related_name="text_assessment")
    audio_questions = models.ManyToManyField(AudioQuestion, related_name="audio_assessment",blank=True)
    fillup_questions = models.ManyToManyField(FillInTheBlank, related_name="fillup_assessment",blank=True)
    level = models.CharField(
        max_length=20, choices=ASSESSMENT_LEVELS, default=ASSESSMENT_LEVELS[0][0]
    )
    sub_level = models.CharField(
        max_length=40, choices=SUB_LEVELS, default=SUB_LEVELS[0][0], blank=True, null=True
    )
    subject = models.CharField(
        max_length=20,
        choices=Subject.choices,
        null=True,
        blank=True,
    )
    show_correct_answer = models.BooleanField(default=False)
    shuffle_question=models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assessment"
    )
    objects = AssessmentManager()
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    @property
    def generate_url(self):
        return f"{DOMAIN}/assessment/{self.id}/{slugify(self.name)}"

    @property
    def total_questions(self):
        return self.questions.count() + self.audio_questions.count()+ self.fillup_questions.count()
    
    @property
    def maximum_marks(self):
        cache_key = f"assessment_maximum_marks_{self.id}"
        max_marks = cache.get(cache_key)
        if max_marks is None:
            max_marks = self.questions.count() + sum([question.maximum_marks for question in self.audio_questions.all()]) + sum([question.maximum_marks for question in self.fillup_questions.all()]) 
            cache.set(cache_key, max_marks, timeout=3600)  # for 1 hour
        return max_marks
    @property
    def get_user(self):
        return AssessmentResult.objects.filter(assessment=self).count()
    
    def delete(self, *args, **kwargs):
        self.questions.all().delete()
        self.audio_questions.all().delete()
        super().delete(*args, **kwargs)


class Answer(models.Model):
    question = models.ForeignKey("Question", on_delete=models.CASCADE, null=True, blank=True)
    selected_option = models.ForeignKey(
        "Option", on_delete=models.CASCADE, null=True, blank=True
    )
    audio_question = models.ForeignKey("AudioQuestion", on_delete=models.CASCADE, null=True, blank=True, related_name="audio_question")
    fillup_question = models.ForeignKey("FillInTheBlank", on_delete=models.CASCADE, null=True, blank=True, related_name="fillup_question")
    fillup_answer = models.JSONField(blank=True, null=True)
    audio_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField(default=False) 
    mark_obtained = models.FloatField(default=0, blank=True, null=True)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        if self.question:
            self.is_correct = self.selected_option == self.question.correct_answer if self.selected_option else False
            self.mark_obtained = 1 if self.is_correct else 0
        elif self.fillup_question:
            correct_answers = self.fillup_question.correct_answer
            your_answers = self.fillup_answer or {}
            self.mark_obtained = 0
            self.is_correct = False
            for key, value in your_answers.items():
                if value == correct_answers.get(key):
                    self.mark_obtained += 1
            if self.mark_obtained == len(correct_answers):
                self.is_correct = True
        elif self.audio_question:
            point, _, is_correct = self.audio_question.is_correct(self.audio_answer)
            self.mark_obtained = point
            self.is_correct = is_correct
        super().save(*args, **kwargs)
    
    def audio_answer_verdict(self):
        return self.audio_question.is_correct(self.audio_answer)[1]

class OrganizationManager(models.Manager):
    def get_all_cached(self):
        cache_key = "all_organizations_id_name"
        orgs = cache.get(cache_key)
        if orgs is None:
            orgs = self.get_queryset().only('id', 'name')
            cache.set(cache_key, orgs, timeout=60*60)  
        return orgs
class Organization(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    logo = models.ImageField(upload_to="organizations", null=True, blank=True)
    created_at = models.DateTimeField(
        default=timezone.now, null=True, blank=True
    )
    history = HistoricalRecords()

    objects = OrganizationManager()
    def __str__(self):
        return self.name

class DisabilityManager(models.Manager):
    def get_all_cached(self):
        cache_key = "all_disabilities_id_name"
        disabilities = cache.get(cache_key)
        if disabilities is None:
            disabilities = self.get_queryset()
            cache.set(cache_key, disabilities, timeout=60*60)  
        return disabilities
class Disability(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    objects = DisabilityManager()

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Disabilities"

class AssessmentResultManager(models.Manager):
    def get_or_filter_answer_with_prefetch(self, option="get", **filters):
        try :
            prefetch = Prefetch(
                "answers",
                queryset=Answer.objects.select_related("question", "audio_question")
            )

            queryset = self.prefetch_related(prefetch)

            if option == "get":
                return queryset.get(**filters)
            elif option == "filter":
                return queryset.filter(**filters)
            else:
                raise ValueError("Option must be either 'get' or 'filter'")
        except AssessmentResult.DoesNotExist:
            logger.error(f"AssessmentResult with filters {filters} does not exist.")
            return None

        
class AssessmentResult(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    education = models.CharField(max_length=255, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True)
    disabiliity = models.ForeignKey(Disability, on_delete=models.CASCADE, null=True, blank=True)
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="result"
    )
    def default_score():
        return {'total_score': 0}
    score = models.IntegerField()
    new_score = models.JSONField(default=default_score)
    grade = models.CharField(max_length=20, choices=GRADES, default=GRADES[0][0])
    total_questions = models.IntegerField(default=0)
    attempted_questions = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    answers = models.ManyToManyField(Answer, related_name="assessment_results")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(
        default=timezone.now, null=True, blank=True
    )
    objects = AssessmentResultManager()
    history = HistoricalRecords()
        
    def __str__(self):
        return f"{self.name}'s Result for {self.assessment.name[:20]}"
    
    @property
    def generate_url(self):
        return f"{DOMAIN}/result-page/{self.id}/"
    
    @classmethod
    def create(
                cls,name,email,education,organization,disabiliity,
                assessment,attempted_questions,total_questions,
                grade,start_time,end_time
                ):
        logger.info("Creating AssessmentResult instance")
        try:
            assessment_result = cls(
                name=name,
                email=email,
                education=education,
                organization=organization,
                disabiliity=disabiliity,
                assessment=assessment,
                grade=grade,
                score=0,  # Default score, can be updated later
                attempted_questions=attempted_questions,
                total_questions=total_questions,
                start_time=start_time,
                end_time=end_time,
            )
            assessment_result.save()  
        except Exception as e:
            assessment_result = None
            logger.error(f"Error creating AssessmentResult instance: {e}")
        return assessment_result
    
    def save(self, *args, **kwargs):
        """Validate the AssessmentResult instance before saving."""
        if self.start_time > self.end_time:
            raise ValidationError("Start time cannot be after end time.")
        if self.attempted_questions > self.total_questions:
            raise ValidationError("Attempted questions cannot exceed total questions.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.answers.all().delete()
        super().delete(*args, **kwargs)

class AssessmentJob(models.Model):
    job_id = models.CharField(max_length=100, unique=True, db_index=True)
    assessment_id = models.IntegerField()
    email = models.EmailField()
    name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=40, choices=StatusChoices, default=StatusChoices[0][0])
    payload = models.JSONField()
    result_id = models.IntegerField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['job_id'], name='idx_assessment_job_id'),
            models.Index(fields=['assessment_id', 'email'], name='idx_assessment_email'),
            models.Index(fields=['status'], name='idx_assessment_status'),
        ]
    
    def __str__(self):
        return f"Job {self.job_id} - {self.email}"