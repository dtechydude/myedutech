from django.urls import path

from . import views

# Mount in the PROJECT urls.py (not inside elearning/urls.py, whose generic
# '<slug>/' patterns would swallow these):
#     path('lesson-notes/', include('elearning.lessonnotes.urls')),
app_name = 'lessonnotes'

urlpatterns = [
    path('', views.HomeRedirectView.as_view(), name='home'),
    path('mine/', views.MyNotesView.as_view(), name='mine'),
    path('submit/', views.NoteCreateView.as_view(), name='submit'),
    path('all/', views.AllNotesView.as_view(), name='all'),
    path('teachers/', views.TeacherSummaryView.as_view(), name='teachers'),
    path('teachers/<int:teacher_id>/', views.AllNotesView.as_view(), name='teacher_notes'),
    path('export/', views.ExportView.as_view(), name='export'),
    path('<int:pk>/', views.NoteDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.NoteUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.NoteDeleteView.as_view(), name='delete'),
    path('<int:pk>/review/', views.NoteReviewView.as_view(), name='review'),
]