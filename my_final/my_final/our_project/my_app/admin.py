from django.contrib import admin

from .models import (
    Answer,
    Choice,
    Profile,
    Question,
    Response,
    Section,
    Survey,
)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1
    fields = ('text', 'is_correct')
    list_display = ('text', 'is_correct')


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    show_change_link = True


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'survey', 'question_type', 'required')
    list_filter = ('question_type', 'required')
    inlines = [ChoiceInline]


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'survey_type',
        'assigned_sections_display',
        'created_by',
        'due_date',
        'is_active',
        'created_at',
        'response_count',
    )
    list_filter = ('is_active', 'survey_type', 'assigned_sections', 'created_at')
    search_fields = ('title', 'description')
    list_select_related = ('created_by',)
    filter_horizontal = ('assigned_sections',)
    inlines = [QuestionInline]

    @admin.display(description='Sections')
    def assigned_sections_display(self, obj):
        sections = obj.assigned_sections.all()
        if sections:
            return ', '.join([s.name for s in sections])
        return 'All sections'

    @admin.display(ordering='created_at', description='Responses')
    def response_count(self, obj):
        return obj.responses.count()


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    can_delete = False


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('survey', 'student', 'submitted_at', 'answer_count')
    list_filter = ('submitted_at',)
    search_fields = ('survey__title', 'student__username')
    list_select_related = ('survey', 'student')
    inlines = [AnswerInline]

    @admin.display(description='Answers')
    def answer_count(self, obj):
        return obj.answers.count()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'section')
    list_filter = ('role', 'section')
    search_fields = ('user__username', 'user__email', 'section__name')
    autocomplete_fields = ('section',)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


admin.site.register(Choice)
admin.site.register(Answer)


