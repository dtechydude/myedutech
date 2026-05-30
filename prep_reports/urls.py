"""
KwikSchools — Prep Report Card URL Configuration
=================================================
Include in your main urls.py:
    path('prep-reports/', include('prep_reports.urls', namespace='prep_reports')),
"""

from django.urls import path
from . import views

app_name = 'prep_reports'

urlpatterns = [
    # --- Dashboard ---
    path(
        '',
        views.PrepDashboardView.as_view(),
        name='dashboard'
    ),

    # --- Period & class selector ---
    path(
        'select/',
        views.SelectPeriodView.as_view(),
        name='select_period'
    ),

    # --- Class → Student list ---
    path(
        'class/<int:prep_class_id>/period/<int:period_id>/',
        views.PrepClassStudentListView.as_view(),
        name='class_students'
    ),

    # --- Bulk create report cards for a class ---
    path(
        'class/<int:prep_class_id>/period/<int:period_id>/bulk-create/',
        views.BulkCreateReportCardsView.as_view(),
        name='bulk_create'
    ),

    # --- Edit a single report card ---
    path(
        'report/<int:report_card_id>/edit/',
        views.PrepReportCardEditView.as_view(),
        name='report_card_edit'
    ),

    # --- Preview (read-only) ---
    path(
        'report/<int:report_card_id>/preview/',
        views.PrepReportCardPreviewView.as_view(),
        name='report_card_preview'
    ),

    # --- PDF export ---
    path(
        'report/<int:report_card_id>/pdf/',
        views.PrepReportCardPDFView.as_view(),
        name='report_card_pdf'
    ),

    # --- AJAX: subject skill entry form fragment ---
    path(
        'report/<int:report_card_id>/subject/<int:subject_id>/skills/',
        views.SubjectSkillAjaxView.as_view(),
        name='subject_skills_ajax'
    ),

    # --- Admin: prep class management ---
    path(
        'admin/classes/',
        views.PrepClassListView.as_view(),
        name='admin_class_list'
    ),
]
