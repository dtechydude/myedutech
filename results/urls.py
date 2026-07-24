from django.urls import path
from . import views
# from .views import (
#     ScoreEntryView, ScoreEntrySuccessView, MidTermScoreEntryView, MidTermReportCardView, StudentMidTermListView, MidTermScoreSelectionView, MidTermScoreSuccessView, BroadsheetSelectionView, SessionPublicationControlView,
#     ReportCardListView, StudentReportCardView, StudentDashboardView, SessionReportCardListView, StudentSessionReportCardView, ClassRankingView, StandardsAndTermsListView, ResultPermissionGatekeeperView, SessionCommentClassView# Import new views
# )
from .views import (
    BroadsheetSelectionView,
    ClassRankingView,
    MidTermReportCardView,
    MidTermScoreEntryView,
    MidTermScoreSelectionView,
    MidTermScoreSuccessView,
    ReportCardListView,
    ResultPermissionGatekeeperView,
    ScoreEntrySuccessView,
    ScoreEntryView,
    SessionCommentClassView,
    SessionPublicationControlView,
    SessionReportCardListView,
    StandardsAndTermsListView,
    StudentDashboardView,
    StudentMidTermListView,
    StudentReportCardView,
    StudentSessionReportCardView,
    SessionReportCommentUpdateView,
    BulkSessionReportCardSelectView,
    BulkSessionReportCardView,
    
)

from django.views.generic import TemplateView # For a simple placeholder home page


app_name ='results'

urlpatterns = [
   
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

     # PARENT RESULTS ACCESS
    path('parent/mid-term/<int:student_id>/<int:term_id>/', 
     views.ParentMidTermReportView.as_view(), name='parent_mid_term_report'),

    path('parent/termly-report/<int:student_id>/<int:term_id>/', 
     views.ParentTermlyReportView.as_view(), 
     name='parent_termly_report'),

    path('parent/session-report/<int:student_id>/<int:session_id>/', 
     views.ParentSessionReportView.as_view(), name='parent_session_report'),


    # Annual (Session) Report Card URLs (Teacher/Admin access)
    path('annual-report-cards/', SessionReportCardListView.as_view(), name='session_report_card_list'),
    path('annual-report-cards/<int:student_id>/<int:session_id>/', StudentSessionReportCardView.as_view(), name='student_session_report_card_detail'),
    # Session Report Comment

    path(
        'session-report-card/<int:student_id>/<int:session_id>/comment/',
        SessionReportCommentUpdateView.as_view(),
        name='session_report_comment_update'
    ),
    path(
        'session-comments/<int:session_id>/',
        SessionCommentClassView.as_view(),
        name='session_comment_class_list'
    ),

    path(
        'session-report-card/bulk/',
        BulkSessionReportCardSelectView.as_view(),
        name='session_report_card_bulk_select'
    ),
    path(
        'session-report-card/bulk/<int:session_id>/<int:standard_id>/',
        BulkSessionReportCardView.as_view(),
        name='session_report_card_bulk'
    ),

    # URL for entering/editing motor ability scores
    # path('enter-motor-ability/<int:student_id>/<int:term_id>/', views.MotorAbilityScoreCreateUpdateView.as_view(), name='enter_motor_ability_score'),
    path('student/<int:student_id>/term/<int:term_id>/motor-ability-score/', views.MotorAbilityScoreCreateUpdateView.as_view(), name='motor_ability_score_create_update'),

    # path('parent_session_report_card/<int:student_id>/<int:session_id>/', views.parent_session_report_card_detail, name='parent_session_report_card_detail'),

    #parent to check results
    # path('parent/report-cards/<int:student_id>/<int:term_id>/', views.ParentReportCardView.as_view(), name='parent_report_card_detail'),
    # path('parent/report-cards/<int:student_id>/<int:term_id>/', views.ParentReportCardView.as_view(), name='parent_report_card_detail'),
    
    # New URL for session report card
    # path('parent/session-report-cards/<int:student_id>/<int:session_id>/', views.ParentSessionReportCardView.as_view(), name='parent_session_report_card_detail'),
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
    
    # session result publication
    path('session-publication-control/', views.SessionPublicationControlView.as_view(), name='session_pub_control'),
    
    # Result Broadsheet
    path('broadsheet/select/', views.BroadsheetSelectionView.as_view(), name='broadsheet_select'),
    path('class-broadsheet/<int:class_id>/<int:term_id>/', views.ClassBroadsheetView.as_view(), name='class_broadsheet'),

    # Bulk Report Card Print
    path('bulk-print-selector/', views.BulkReportCardSelectorView.as_view(), name='bulk_report_card_selector'),
    path('bulk-print/<int:standard_id>/<int:term_id>/', views.BulkReportCardPrintView.as_view(), name='bulk_report_card_print'),

]



