from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.http import JsonResponse, HttpResponseForbidden
from .models import (
    Answer,
    Choice,
    Profile,
    Question,
    Response,
    Section,
    Survey,
)
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.dateparse import parse_date
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction, models
from django.views.generic import TemplateView
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import datetime


# === TEACHER VIEWS ===

# Add question to survey
class SurveyQuestionCreateView(LoginRequiredMixin, View):
    def post(self, request, survey_id):
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'teacher':
            return HttpResponseForbidden()

        survey = get_object_or_404(Survey, id=survey_id)
        q_type = request.POST.get('question_type') or 'text'
        question = Question.objects.create(
            survey=survey,
            text=request.POST.get('text', '').strip(),
            question_type=q_type,
        )
        if q_type in ['mcq', 'likert']:
            # accept either 'choices' or 'choices[]' form names
            choices = request.POST.getlist('choices') or request.POST.getlist('choices[]')
            for choice_text in choices:
                if choice_text:
                    Choice.objects.create(question=question, text=choice_text)
        return JsonResponse({'message': 'Question added', 'id': question.id}, status=201)


# === STUDENT VIEWS ===

# View assigned surveys
class AssignedSurveyListView(LoginRequiredMixin, View):
    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return JsonResponse([], safe=False)

        surveys = self._get_open_surveys_for_section(profile.section)
        payload = [
            {
                'id': survey.id,
                'title': survey.title,
                'description': survey.description,
                'due_date': survey.due_date,
            }
            for survey in surveys
        ]
        return JsonResponse(payload, safe=False)

    def _get_open_surveys_for_section(self, section):
        today = timezone.localdate()
        all_surveys = Survey.objects.filter(
            is_active=True
        ).filter(
            models.Q(due_date__isnull=True) | models.Q(due_date__gte=today)
        ).prefetch_related('assigned_sections')
        
        # Filter surveys: show if no assigned sections OR if student's section is in assigned sections
        filtered_surveys = []
        for survey in all_surveys:
            if survey.assigned_sections.count() == 0:
                filtered_surveys.append(survey)
            elif section and section in survey.assigned_sections.all():
                filtered_surveys.append(survey)
        
        return filtered_surveys


# Submit survey response
class SubmitSurveyView(LoginRequiredMixin, View):
    def post(self, request, survey_id):
        survey = get_object_or_404(Survey, id=survey_id)
        user = request.user

        if Response.objects.filter(survey=survey, student=user).exists():
            return JsonResponse({'error': 'Already submitted'}, status=400)

        response = Response.objects.create(survey=survey, student=user)
        for question in survey.questions.all():
            answer_key = f'question_{question.id}'
            if question.question_type in ['mcq', 'likert']:
                choice_id = request.POST.get(answer_key)
                if choice_id:
                    # selected_choice_id assignment is okay; cast/validate if needed
                    Answer.objects.create(
                        response=response, question=question, selected_choice_id=choice_id
                    )
            else:
                text_value = request.POST.get(answer_key, '')
                Answer.objects.create(response=response, question=question, text_answer=text_value)
        return JsonResponse({'message': 'Survey submitted successfully'}, status=201)


# View submission history
class StudentHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'my_app/student_history.html'

    def get(self, request, *args, **kwargs):
        if self._wants_json(request):
            responses = self._get_responses(request)
            data = [
                {
                    'survey_title': r.survey.title,
                    'submitted_at': r.submitted_at,
                    'survey_id': r.survey.id,
                    'answers': [
                        {
                            'question': answer.question.text,
                            'response': answer.selected_choice.text if answer.selected_choice else answer.text_answer,
                        }
                        for answer in r.answers.all()
                    ],
                }
                for r in responses
            ]
            return JsonResponse(data, safe=False)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        responses = self._get_responses(self.request)
        profile = getattr(self.request.user, 'profile', None)
        history = []
        for response in responses:
            answer_details = []
            for answer in response.answers.all():
                if answer.selected_choice:
                    value = answer.selected_choice.text
                else:
                    value = answer.text_answer or '—'
                answer_details.append(
                    {
                        'question': answer.question.text,
                        'question_type': answer.question.question_type,
                        'answer': value,
                        'is_correct': answer.is_correct,  # True, False, or None
                        'correct_answer': answer.correct_answer,  # The correct answer text if MCQ
                        'answer_obj': answer,  # Pass the answer object for template access
                    }
                )

            history.append(
                {
                    'survey': response.survey,
                    'submitted_at': response.submitted_at,
                    'answers': answer_details,
                }
            )

        context.update(
            {
                'history': history,
                'response_count': responses.count(),
                'profile': profile,
                'section': profile.section if profile else None,
                'dashboard_url': reverse('student_dashboard'),
            }
        )
        return context

    def _get_responses(self, request):
        return (
            Response.objects.filter(student=request.user)
            .select_related('survey', 'survey__created_by')
            .prefetch_related('answers__question', 'answers__selected_choice', 'survey__assigned_sections')
            .order_by('-submitted_at')
        )

    def _wants_json(self, request):
        accept = request.headers.get('Accept', '')
        return 'application/json' in accept or request.GET.get('format') == 'json'


# === AUTHENTICATION VIEWS ===

class RegisterView(View):
    """Register a new user (teacher or student) and create their Profile."""
    
    def get(self, request):
        """Render registration form with role selection."""
        sections = Section.objects.order_by('name')
        return render(request, 'my_app/register.html', {'sections': sections})
    
    def post(self, request):
        """Handle user registration and profile creation."""
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        role = request.POST.get('role', 'student')  # default to student
        section_id = request.POST.get('section', '').strip()
        
        # Validation
        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        if not email:
            errors['email'] = 'Email is required.'
        if not password:
            errors['password'] = 'Password is required.'
        if password != password_confirm:
            errors['password_confirm'] = 'Passwords do not match.'
        if role not in ['student', 'teacher']:
            errors['role'] = 'Invalid role selected.'
        selected_section = None
        if role == 'student':
            if not section_id:
                errors['section'] = 'Section is required for students.'
            else:
                selected_section = Section.objects.filter(id=section_id).first()
                if not selected_section:
                    errors['section'] = 'Selected section does not exist.'
        
        # Check if username/email already exists
        if User.objects.filter(username=username).exists():
            errors['username'] = 'Username already taken.'
        if User.objects.filter(email=email).exists():
            errors['email'] = 'Email already registered.'
        
        if errors:
            return JsonResponse({'errors': errors}, status=400)
        
        # Create user and profile within a transaction
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )
                # Profile is auto-created by post_save signal, just update it
                user.profile.role = role
                if role == 'student':
                    user.profile.section = selected_section
                else:
                    user.profile.section = None
                user.profile.save()
            
            # Auto-login after registration (optional)
            login(request, user)
            # Redirect to appropriate dashboard based on role
            if role == 'teacher':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class LoginView(View):
    """Login view for both teacher and student."""

    def get(self, request):
        """Render login form."""
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            return redirect(self._default_redirect(profile))

        form = AuthenticationForm()
        next_url = request.GET.get('next', '')
        return render(request, 'my_app/login.html', {'form': form, 'next': next_url})

    def post(self, request):
        """Handle user login."""
        next_url = request.POST.get('next', '')
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            profile = getattr(user, 'profile', None)
            redirect_url = self._get_safe_redirect_url(request, next_url, profile)
            return redirect(redirect_url)

        return render(request, 'my_app/login.html', {'form': form, 'next': next_url})

    def _get_safe_redirect_url(self, request, next_url, profile):
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url

        return self._default_redirect(profile)

    def _default_redirect(self, profile):
        if profile and profile.role == 'teacher':
            return reverse('teacher_dashboard')
        if profile and profile.role == 'student':
            return reverse('student_dashboard')
        return reverse('home')


class LogoutView(LoginRequiredMixin, View):
    """Logout view."""
    
    def post(self, request):
        """Handle user logout."""
        logout(request)
        return JsonResponse({'message': 'Logged out successfully.'}, status=200)
    
    def get(self, request):
        """Allow GET for convenience (though POST is safer)."""
        logout(request)
        return redirect('login')


class CurrentUserView(LoginRequiredMixin, View):
    """Return current logged-in user info (profile, role, etc)."""
    
    def get(self, request):
        """Get current user details."""
        profile = getattr(request.user, 'profile', None)
        return JsonResponse({
            'user_id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'role': profile.role if profile else 'unknown',
            'section': profile.section.name if profile and profile.section else None,
        }, status=200)


# === DASHBOARDS ===

class HomeView(View):
    """Home/landing page that redirects to appropriate dashboard."""
    
    def get(self, request):
        """Redirect to dashboard if logged in, else show home."""
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile:
                if profile.role == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
        return render(request, 'my_app/home.html')


# === SURVEY BUILDER (TEACHER) ===

class CreateSurveyFormView(LoginRequiredMixin, View):
    """Create a new survey form."""
    
    def get(self, request):
        """Show create survey form."""
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'teacher':
            return redirect('login')
        context = self._build_context()
        return render(request, 'my_app/survey_create.html', context)
    
    def post(self, request):
        """Handle survey creation."""
        profile = getattr(request.user, 'profile', None)
        if not profile or profile.role != 'teacher':
            return redirect('login')
        
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        section_ids = request.POST.getlist('assigned_sections')  # Get multiple sections
        survey_type_id = request.POST.get('survey_type', '').strip()
        due_date_str = request.POST.get('due_date', '')
        context = self._build_context(form_data=request.POST)
        
        # Validation
        if not title:
            context['error'] = 'Title is required'
            return render(request, 'my_app/survey_create.html', context)
        
        # Validate survey type
        valid_types = [choice[0] for choice in Survey.SURVEY_TYPE_CHOICES]
        if survey_type_id not in valid_types:
            context['error'] = 'Please choose a valid survey type.'
            return render(request, 'my_app/survey_create.html', context)
        
        due_date = parse_date(due_date_str) if due_date_str else None
        
        # Create survey
        survey = Survey.objects.create(
            title=title,
            description=description,
            created_by=request.user,
            survey_type=survey_type_id,
            due_date=due_date,
            is_active=True
        )
        
        # Assign sections (can be empty for "all sections")
        if section_ids:
            sections = Section.objects.filter(id__in=section_ids)
            survey.assigned_sections.set(sections)
        
        return redirect('edit_survey', survey_id=survey.id)

    def _build_context(self, form_data=None):
        context = {
            'sections': Section.objects.order_by('name'),
            'survey_types': Survey.SURVEY_TYPE_CHOICES,
        }
        if form_data:
            context['form_data'] = {
                'title': form_data.get('title', ''),
                'description': form_data.get('description', ''),
                'survey_type': form_data.get('survey_type', ''),
                'assigned_sections': form_data.getlist('assigned_sections'),
                'due_date': form_data.get('due_date', ''),
            }
        return context


class EditSurveyView(LoginRequiredMixin, TemplateView):
    """Edit survey details and add/remove questions."""
    template_name = 'my_app/survey_edit.html'
    
    def get_context_data(self, survey_id, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = get_object_or_404(Survey, id=survey_id, created_by=self.request.user)
        questions = survey.questions.all().prefetch_related('choices')
        
        context['survey'] = survey
        context['questions'] = questions
        context['question_types'] = Question.QUESTION_TYPES
        context['sections'] = Section.objects.order_by('name')
        context['survey_types'] = Survey.SURVEY_TYPE_CHOICES
        
        return context
    
    def post(self, request, survey_id):
        """Update survey details."""
        survey = get_object_or_404(Survey, id=survey_id, created_by=request.user)
        
        survey.title = request.POST.get('title', survey.title).strip()
        survey.description = request.POST.get('description', '').strip()
        
        section_ids = request.POST.getlist('assigned_sections')  # Get multiple sections
        survey_type_id = request.POST.get('survey_type', '').strip()
        
        due_date_str = request.POST.get('due_date', '')
        if due_date_str:
            survey.due_date = parse_date(due_date_str)
        
        is_active = request.POST.get('is_active') == 'on'
        survey.is_active = is_active
        
        # Update assigned sections
        if section_ids:
            sections = Section.objects.filter(id__in=section_ids)
            survey.assigned_sections.set(sections)
        else:
            survey.assigned_sections.clear()  # Empty means all sections

        # Validate and set survey type
        if survey_type_id:
            valid_types = [choice[0] for choice in Survey.SURVEY_TYPE_CHOICES]
            if survey_type_id in valid_types:
                survey.survey_type = survey_type_id
            else:
                survey.survey_type = None
        else:
            survey.survey_type = None
        
        survey.save()
        
        return redirect('edit_survey', survey_id=survey.id)


class AddQuestionView(LoginRequiredMixin, View):
    """Add a question to a survey."""
    
    def post(self, request, survey_id):
        """Handle adding question to survey."""
        survey = get_object_or_404(Survey, id=survey_id, created_by=request.user)
        
        question_text = request.POST.get('question_text', '').strip()
        question_type = request.POST.get('question_type', 'text')
        required = request.POST.get('required') == 'on'
        
        if not question_text:
            return redirect('edit_survey', survey_id=survey_id)
        
        question = Question.objects.create(
            survey=survey,
            text=question_text,
            question_type=question_type,
            required=required
        )
        
        # Add choices if MCQ or Likert
        if question_type in ['mcq', 'likert']:
            choices_data = request.POST.getlist('choices')
            for choice_text in choices_data:
                choice_text = choice_text.strip()
                if choice_text:
                    Choice.objects.create(question=question, text=choice_text)
        
        return redirect('edit_survey', survey_id=survey_id)


class EditQuestionView(LoginRequiredMixin, View):
    """Edit a question in a survey."""
    
    def post(self, request, survey_id, question_id):
        """Update question."""
        survey = get_object_or_404(Survey, id=survey_id, created_by=request.user)
        question = get_object_or_404(Question, id=question_id, survey=survey)
        
        question.text = request.POST.get('text', question.text).strip()
        question.required = request.POST.get('required') == 'on'
        question.save()
        
        # Update choices if MCQ or Likert
        if question.question_type in ['mcq', 'likert']:
            # Clear old choices
            question.choices.all().delete()
            # Add new choices
            choices_data = request.POST.getlist('choices')
            for choice_text in choices_data:
                choice_text = choice_text.strip()
                if choice_text:
                    Choice.objects.create(question=question, text=choice_text)
        
        return redirect('edit_survey', survey_id=survey_id)


class DeleteQuestionView(LoginRequiredMixin, View):
    """Delete a question from a survey."""
    
    def post(self, request, survey_id, question_id):
        """Delete question."""
        survey = get_object_or_404(Survey, id=survey_id, created_by=request.user)
        question = get_object_or_404(Question, id=question_id, survey=survey)
        question.delete()
        
        return redirect('edit_survey', survey_id=survey_id)


class DeleteSurveyView(LoginRequiredMixin, View):
    """Delete an entire survey."""
    
    def post(self, request, survey_id):
        """Delete survey."""
        survey = get_object_or_404(Survey, id=survey_id, created_by=request.user)
        survey.delete()
        
        return redirect('teacher_dashboard')


class SurveyResponsesAnalyticsView(LoginRequiredMixin, TemplateView):
    """View survey responses and analytics with pagination, search, and date filtering."""
    template_name = 'my_app/survey_responses.html'
    
    def get_context_data(self, survey_id, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = get_object_or_404(Survey, id=survey_id, created_by=self.request.user)
        
        # Get all responses for this survey
        responses = Response.objects.filter(survey=survey).select_related('student').prefetch_related('answers__question', 'answers__selected_choice').order_by('-submitted_at')
        
        # Apply search filter (by student name/username)
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            responses = responses.filter(
                Q(student__username__icontains=search_query) |
                Q(student__first_name__icontains=search_query) |
                Q(student__last_name__icontains=search_query) |
                Q(student__email__icontains=search_query)
            )
        
        # Apply date filter
        date_from = self.request.GET.get('date_from', '').strip()
        date_to = self.request.GET.get('date_to', '').strip()
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                responses = responses.filter(submitted_at__date__gte=date_from_obj)
            except ValueError:
                pass
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                responses = responses.filter(submitted_at__date__lte=date_to_obj)
            except ValueError:
                pass
        
        # Get total count before pagination
        total_responses = responses.count()
        questions = survey.questions.all().prefetch_related('choices')
        
        # Pagination
        paginator = Paginator(responses, 10)  # 10 responses per page
        page_number = self.request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context['survey'] = survey
        context['total_responses'] = total_responses
        context['responses'] = page_obj
        context['questions'] = questions
        context['page_obj'] = page_obj
        context['search_query'] = search_query
        context['date_from'] = date_from
        context['date_to'] = date_to
        
        return context


class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    """Teacher dashboard - create and manage surveys."""
    template_name = 'my_app/teacher_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'profile', None)
        
        # Check if user is a teacher
        if not profile or profile.role != 'teacher':
            raise HttpResponseForbidden("Access denied. Only teachers can access this page.")
        
        # Get all surveys created by this teacher
        surveys = (
            Survey.objects.filter(created_by=self.request.user)
            .prefetch_related('assigned_sections')
            .order_by('-created_at')
        )
        
        context['surveys'] = surveys
        context['total_surveys'] = surveys.count()
        context['total_responses'] = Response.objects.filter(survey__created_by=self.request.user).count()
        
        return context


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """Student dashboard - view assigned surveys and submit responses."""
    template_name = 'my_app/student_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'profile', None)
        
        # Check if user is a student
        if not profile or profile.role != 'student':
            raise HttpResponseForbidden("Access denied. Only students can access this page.")
        
        # Determine which tab the student wants to view
        requested_tab = self.request.GET.get('tab', 'overview').lower()
        allowed_tabs = {'overview', 'pending', 'completed'}
        active_tab = requested_tab if requested_tab in allowed_tabs else 'overview'
        
        # Get surveys assigned to this student's section
        # Surveys with no assigned_sections are available to all students
        # Surveys with assigned_sections are only available to students in those sections
        all_active_surveys = Survey.objects.filter(is_active=True).prefetch_related('assigned_sections')
        
        assigned_surveys = []
        for survey in all_active_surveys:
            # If survey has no assigned sections, it's available to all
            if survey.assigned_sections.count() == 0:
                assigned_surveys.append(survey)
            elif profile.section and profile.section in survey.assigned_sections.all():
                # If student's section is in the assigned sections
                assigned_surveys.append(survey)
        
        # Convert to queryset for consistency
        survey_ids = [s.id for s in assigned_surveys]
        assigned_surveys = Survey.objects.filter(id__in=survey_ids).prefetch_related('assigned_sections').order_by('-created_at')
        
        # Get student's responses
        submitted_surveys = Response.objects.filter(student=self.request.user).values_list('survey_id', flat=True)
        
        # Separate pending and completed surveys
        pending_surveys = assigned_surveys.exclude(id__in=submitted_surveys)
        completed_surveys = assigned_surveys.filter(id__in=submitted_surveys)
        
        context['pending_surveys'] = pending_surveys
        context['completed_surveys'] = completed_surveys
        context['total_assigned'] = assigned_surveys.count()
        context['total_completed'] = completed_surveys.count()
        context['section'] = profile.section
        context['active_tab'] = active_tab
        context['show_pending'] = active_tab in ('overview', 'pending')
        context['show_completed'] = active_tab in ('overview', 'completed')
        
        return context


class SurveyDetailView(LoginRequiredMixin, TemplateView):
    """View survey details with all questions for students to fill."""
    template_name = 'my_app/survey_detail.html'
    
    def get_context_data(self, survey_id, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'profile', None)
        
        # Get survey
        survey = get_object_or_404(Survey, id=survey_id)
        
        # Check if student has already submitted
        existing_response = Response.objects.filter(
            survey=survey, student=self.request.user
        ).first()
        
        if existing_response:
            context['already_submitted'] = True
            context['submitted_at'] = existing_response.submitted_at
            # Get student's answers
            answers = existing_response.answers.all()
            context['answers'] = answers
        
        # Get all questions with their choices
        questions = survey.questions.all().prefetch_related('choices')
        
        context['survey'] = survey
        context['questions'] = questions
        context['profile'] = profile
        context['section'] = profile.section if profile else None
        
        return context
    
    def post(self, request, survey_id):
        """Handle survey submission."""
        profile = getattr(request.user, 'profile', None)
        
        # Check if student
        if not profile or profile.role != 'student':
            return redirect('login')
        
        survey = get_object_or_404(Survey, id=survey_id)
        
        # Check if already submitted
        if Response.objects.filter(survey=survey, student=request.user).exists():
            return redirect('survey_detail', survey_id=survey_id)
        
        # Create response and answers
        response = Response.objects.create(survey=survey, student=request.user)
        
        for question in survey.questions.all():
            answer_key = f'question_{question.id}'
            
            if question.question_type in ['mcq', 'likert']:
                choice_id = request.POST.get(answer_key)
                if choice_id:
                    try:
                        choice = Choice.objects.get(id=choice_id, question=question)
                        Answer.objects.create(
                            response=response,
                            question=question,
                            selected_choice=choice
                        )
                    except Choice.DoesNotExist:
                        pass
            else:  # text answer
                text_value = request.POST.get(answer_key, '').strip()
                if text_value:
                    Answer.objects.create(
                        response=response,
                        question=question,
                        text_answer=text_value
                    )
        
        # Redirect back with success message
        return redirect('survey_detail', survey_id=survey_id)
