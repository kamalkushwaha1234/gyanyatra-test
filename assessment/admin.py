from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin
from simple_history.admin import SimpleHistoryAdmin

admin.site.register(AssessmentJob)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'is_staff', 'is_active','is_creator')
    list_filter = ('is_staff', 'is_active','is_creator')
    fieldsets = (
        (None, {'fields': ('email','first_name','last_name','date_joined','password')}),
        ('Permissions', {'fields': ('is_staff', 'is_active','is_superuser','is_creator')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active','is_superuser','is_creator')}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)
admin.site.register(User, CustomUserAdmin)

@admin.register(Question)
class QuestionAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ('question', 'level', 'correct_answer')
    list_filter = ('level', 'subject')
    search_fields = ('question', 'content__content')
    ordering = ('level', 'content')
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('content',)

    def delete_queryset(self, request, queryset):
        for question in queryset:
            question.options.all().delete()
        return super().delete_queryset(request, queryset)

@admin.register(FillInTheBlank)
class FillInTheBlankAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ( 'sentence', 'level', 'correct_answer')
    list_filter = ('level', 'subject')
    search_fields = ('sentence', 'content__content')
    ordering = ('level', 'content')
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('content',)
    

@admin.register(AudioQuestion)
class AudioQuestionAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ( 'answer', 'question', 'level')
    list_filter = ('level', 'subject')
    search_fields = ('question', 'content__content')
    ordering = ('level', 'content')
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('content',)

@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ('id','option', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('option',)
    ordering = ('option',)
    list_editable = ('is_correct',)
    list_per_page = 25
    list_max_show_all = 100

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ('content',)
    search_fields = ('content',)
    ordering = ('content',)
    list_per_page = 25
    list_max_show_all = 100

@admin.register(Answer)
class AnswerAdmin(SimpleHistoryAdmin,admin.ModelAdmin):
    list_display = ('question', 'selected_option', 'is_correct')
    list_filter = ('is_correct',)
    search_fields = ('question__question', 'selected_option__option')
    ordering = ('question',)
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('question', 'selected_option')

@admin.register(Assessment)
class AssessmentAdmin(SimpleHistoryAdmin,admin.ModelAdmin):
    list_display = ('name', 'level', 'subject', 'author', 'active')
    list_filter = ('level', 'subject', 'active')
    search_fields = ('name', 'author__email')
    ordering = ('level', 'subject', 'active')
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('author',)

@admin.register(AssessmentResult)
class AssessmentResultAdmin(SimpleHistoryAdmin,admin.ModelAdmin):
    list_display = ('name', 'email', 'assessment', 'score','new_score', 'grade', 'total_questions', 'attempted_questions','start_time','end_time')
    list_filter = ('assessment', 'grade')
    search_fields = ('name', 'email', 'assessment__name')
    ordering = ('assessment', 'grade',)
    list_per_page = 25
    list_max_show_all = 100
    list_select_related = ('assessment',)

    def delete_queryset(self, request, queryset):
        for result in queryset:
            result.answers.all().delete()
        return super().delete_queryset(request, queryset)

@admin.register(Organization)
class OrganizationAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25
    list_max_show_all = 100

@admin.register(Disability)
class DisabilityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)
    list_per_page = 25
    list_max_show_all = 100
