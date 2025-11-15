from django.urls import path
from . import views

urlpatterns = [
    # Home page
    path('', views.HomeView.as_view(), name='home'),
    
    # Authentication endpoints
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('api/me/', views.CurrentUserView.as_view(), name='current_user'),

    # Dashboards
    path('dashboard/teacher/', views.TeacherDashboardView.as_view(), name='teacher_dashboard'),
    path('dashboard/student/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('survey/<int:survey_id>/', views.SurveyDetailView.as_view(), name='survey_detail'),

    # Survey Builder (Teacher)
    path('survey/create/', views.CreateSurveyFormView.as_view(), name='create_survey_form'),
    path('survey/<int:survey_id>/edit/', views.EditSurveyView.as_view(), name='edit_survey'),
    path('survey/<int:survey_id>/add_question/', views.SurveyQuestionCreateView.as_view(), name='add_question'),
    path('survey/<int:survey_id>/question/<int:question_id>/edit/', views.EditQuestionView.as_view(), name='edit_question'),
    path('survey/<int:survey_id>/question/<int:question_id>/delete/', views.DeleteQuestionView.as_view(), name='delete_question'),
    path('survey/<int:survey_id>/delete/', views.DeleteSurveyView.as_view(), name='delete_survey'),
    path('survey/<int:survey_id>/responses/', views.SurveyResponsesAnalyticsView.as_view(), name='survey_responses'),

    # Student endpoints
    path('student/surveys/', views.AssignedSurveyListView.as_view(), name='assigned_surveys'),
    path('survey/<int:survey_id>/submit/', views.SubmitSurveyView.as_view(), name='submit_survey'),
    path('student/history/', views.StudentHistoryView.as_view(), name='student_history'),
]
