from django.urls import path
from . import views

# =====================================================================
# ✅ Fully independent namespace
# ---------------------------------------------------------------------
# app_name = 'elearning' — this app is no longer piggy-backing on the
# 'curriculum' namespace. Mount this urls.py at its OWN prefix in your
# project's root urls.py, e.g.:
#
#     path('elearning/', include('elearning.urls')),
#
# Any existing template that calls {% url 'curriculum:lesson_detail' %}
# (or lesson_list / lesson_create / lesson_update / lesson_delete /
# standard_list / subject_list / my-standard) needs to be updated to
# {% url 'elearning:lesson_detail' %} etc. — see the README for a grep
# command to find every place that needs updating.
# =====================================================================

app_name = 'elearning'

urlpatterns = [
    path('', views.ClassListView.as_view(), name='standard_list'),
    path('my-standard/', views.StandardSelfListView.as_view(), name='my-standard'),
    path('<slug:slug>/', views.SubjectListView.as_view(), name='subject_list'),
    path('<str:standard>/<slug:slug>/', views.LessonListView.as_view(), name='lesson_list'),
    path('<str:standard>/<str:slug>/create/', views.LessonCreateView.as_view(), name='lesson_create'),
    path('<str:standard>/<str:subject>/<slug:slug>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('<str:standard>/<str:subject>/<slug:slug>/update/', views.LessonUpdateView.as_view(), name='lesson_update'),
    path('<str:standard>/<str:subject>/<slug:slug>/delete/', views.LessonDeleteView.as_view(), name='lesson_delete'),

    # Assignments / Homework
    path('<str:standard>/<str:subject>/<slug:lesson_slug>/assignment/create/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('<str:standard>/<str:subject>/<slug:lesson_slug>/assignment/<slug:slug>/update/', views.AssignmentUpdateView.as_view(), name='assignment_update'),
    path('<str:standard>/<str:subject>/<slug:lesson_slug>/assignment/<slug:slug>/delete/', views.AssignmentDeleteView.as_view(), name='assignment_delete'),
]
