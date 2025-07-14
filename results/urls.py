from django.urls import path
from . import views
from .views import (
    ScoreEntryView, ScoreEntrySuccessView,
    ReportCardListView, StudentReportCardView, StudentDashboardView, SessionReportCardListView, StudentSessionReportCardView # Import new views
)

from django.views.generic import TemplateView # For a simple placeholder home page


app_name ='results'

urlpatterns = [
   
    # Path for students to see a list of all terms they have results for
    path('my_results/terms/', views.my_term_results_view, name='my_terms_list'),

    # Path for students to see detailed results for a specific term
    # This might be the one you previously called 'my_term_results_view' or similar
    path('my_results/term/<int:term_id>/', views.my_term_results_view, name='my_term_results'),

    # Path for the consolidated report card for a specific term
    # path('my_results/term/<int:term_id>/report_card/', views.student_term_report_card_view, name='student_term_report_card'),
    path('student/<int:student_id>/session/<int:session_id>/report/', views.student_session_report_view, name='student_session_report'),

    #working well 001
    path('score-entry/', ScoreEntryView.as_view(), name='score_entry'),
    path('score-entry/success/', ScoreEntrySuccessView.as_view(), name='score_entry_success'),

    # Report Card URLs (Teacher/Admin access)
    path('report-cards/', ReportCardListView.as_view(), name='report_card_list'),
    path('report-cards/<int:student_id>/<int:term_id>/', StudentReportCardView.as_view(), name='student_report_card_detail'),

    # Student Dashboard URL (for students to view their own report cards)
    path('student-dashboard/', StudentDashboardView.as_view(), name='student_dashboard'),


    # # Placeholder for a home page (create templates/home.html)
    # path('', TemplateView.as_view(template_name='home.html'), name='home'), 
    # # This 'home' URL name is used in report_card_detail.html and StudentDashboardView fallback
    # path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='some_general_dashboard_or_home_page'), # Fallback for unlinked users

    # Annual (Session) Report Card URLs (Teacher/Admin access)
    path('annual-report-cards/', SessionReportCardListView.as_view(), name='session_report_card_list'),
    path('annual-report-cards/<int:student_id>/<int:session_id>/', StudentSessionReportCardView.as_view(), name='student_session_report_card_detail'),

    # URL for entering/editing motor ability scores
    path('enter-motor-ability/<int:student_id>/<int:term_id>/', views.MotorAbilityScoreCreateUpdateView.as_view(), name='enter_motor_ability_score'),


]


