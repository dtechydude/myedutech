from django.urls import path
from . import views
from .views import (
    ScoreEntryView, ScoreEntrySuccessView, MidTermScoreEntryView, MidTermReportCardView, StudentMidTermListView, MidTermScoreSelectionView, MidTermScoreSuccessView,
    ReportCardListView, StudentReportCardView, StudentDashboardView, SessionReportCardListView, StudentSessionReportCardView, ClassRankingView, StandardsAndTermsListView, ResultPermissionGatekeeperView # Import new views
)

from django.views.generic import TemplateView # For a simple placeholder home page


app_name ='results'

urlpatterns = [
   
    # Path for students to see a list of all terms they have results for
    # path('my_results/terms/', views.my_term_results_view, name='my_terms_list'),

    # Path for students to see detailed results for a specific term
    # This might be the one you previously called 'my_term_results_view' or similar
    # path('my_results/term/<int:term_id>/', views.my_term_results_view, name='my_term_results'),

    # Path for the consolidated report card for a specific term
    # path('my_results/term/<int:term_id>/report_card/', views.student_term_report_card_view, name='student_term_report_card'),
    # path('student/<int:student_id>/session/<int:session_id>/report/', views.student_session_report_view, name='student_session_report'),

    #working well 001
    path('score-entry/', ScoreEntryView.as_view(), name='score_entry'),
    path('score-entry/success/', ScoreEntrySuccessView.as_view(), name='score_entry_success'),

    # Report Card URLs (Teacher/Admin access)
    path('report-cards/', ReportCardListView.as_view(), name='report_card_list'),
 
    path('report-cards/<int:student_id>/<int:term_id>/', StudentReportCardView.as_view(), name='student_report_card_detail'),
    
    path('class-ranking/<int:standard_id>/<int:term_id>/', ClassRankingView.as_view(), name='class_ranking'),
    path('ranking-list/', StandardsAndTermsListView.as_view(), name='ranking_list'),

    # Student Dashboard URL (for students to view their own report cards)
    path('student-dashboard/', StudentDashboardView.as_view(), name='student_dashboard'),

    # Result publication permission
    path('results/report-cards/<int:student_id>/<int:term_id>/', 
     ResultPermissionGatekeeperView.as_view(), # <-- Must use the gatekeeper
     name='student_report_card_detail'),


    # # Placeholder for a home page (create templates/home.html)
    # path('', TemplateView.as_view(template_name='home.html'), name='home'), 
    # # This 'home' URL name is used in report_card_detail.html and StudentDashboardView fallback
    # path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='some_general_dashboard_or_home_page'), # Fallback for unlinked users

    # Annual (Session) Report Card URLs (Teacher/Admin access)
    path('annual-report-cards/', SessionReportCardListView.as_view(), name='session_report_card_list'),
    path('annual-report-cards/<int:student_id>/<int:session_id>/', StudentSessionReportCardView.as_view(), name='student_session_report_card_detail'),

    # URL for entering/editing motor ability scores
    # path('enter-motor-ability/<int:student_id>/<int:term_id>/', views.MotorAbilityScoreCreateUpdateView.as_view(), name='enter_motor_ability_score'),
    path('student/<int:student_id>/term/<int:term_id>/motor-ability-score/', views.MotorAbilityScoreCreateUpdateView.as_view(), name='motor_ability_score_create_update'),

    path('parent_session_report_card/<int:student_id>/<int:session_id>/', views.parent_session_report_card_detail, name='parent_session_report_card_detail'),

    #parent to check results
    # path('parent/report-cards/<int:student_id>/<int:term_id>/', views.ParentReportCardView.as_view(), name='parent_report_card_detail'),
    path('parent/report-cards/<int:student_id>/<int:term_id>/', views.ParentReportCardView.as_view(), name='parent_report_card_detail'),
    
    # New URL for session report card
    path('parent/session-report-cards/<int:student_id>/<int:session_id>/', views.ParentSessionReportCardView.as_view(), name='parent_session_report_card_detail'),
    # ... other URL patterns


    # 1. SCORE ENTRY PAGE (Teacher/Admin access)
    # 1. New List View for Students (Student accesses this first)
    path('midterm/score/select/', 
         MidTermScoreSelectionView.as_view(), 
         name='midterm_score_selection'),
    path('midterm/reports/', 
         StudentMidTermListView.as_view(), 
         name='student_midterm_list'),
    # The URL needs to carry the class, subject, and term IDs to define the score sheet
    # path('midterm/score/entry/<int:class_id>/<int:subject_id>/<int:term_id>/', 
    #      MidTermScoreEntryView.as_view(), 
    #      name='midterm_score_entry'),
    path(
        'midterm/score/entry/<int:class_id>/<int:subject_id>/<int:term_id>/',
        views.MidTermScoreEntryView.as_view(),
        name='midterm_score_entry'
    ),

    path('midterm/score/success/<int:class_id>/<int:subject_id>/<int:term_id>/', 
     MidTermScoreSuccessView.as_view(), 
     name='midterm_score_success'),
         
    # You will likely need a selection page (e.g., 'teacher_midterm_select')
    # to choose class/subject/term before hitting the entry page.

    # 2. REPORT CARD VIEW (Student/Teacher/Admin access)
    path('midterm/report/<int:student_id>/<int:term_id>/', 
         MidTermReportCardView.as_view(), 
         name='midterm_report_card_detail'),

    path('result-publications/', views.result_publications_list, name='result_publications_list'),
    path('result-publications/toggle/<int:pk>/', views.toggle_publication_status, name='toggle_publication_status'),
    path('result-publications/bulk/', views.bulk_update_publications, name='bulk_update_publications'),
]



