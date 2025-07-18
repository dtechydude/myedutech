from django.urls import path
from . import views
from curriculum import views as curriculum_view


app_name = 'curriculum'

urlpatterns = [
    path('', views.ClassListView.as_view(), name='standard_list'),
    path('my-standard/', views.StandardSelfListView.as_view(), name='my-standard'),
    path('<slug:slug>/', views.SubjectListView.as_view(), name='subject_list'),
    path('<str:standard>/<slug:slug>/', views.LessonListView.as_view(), name='lesson_list'),
    path('<str:standard>/<str:slug>/create/', views.LessonCreateView.as_view(), name='lesson_create'),
    path('<str:standard>/<str:subject>/<slug:slug>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('<str:standard>/<str:subject>/<slug:slug>/update/', views.LessonUpdateView.as_view(), name='lesson_update'),
    path('<str:standard>/<str:subject>/<slug:slug>/delete/', views.LessonDeleteView.as_view(), name='lesson_delete'),

    path('class-list/', curriculum_view.class_list, name="class_list"),

    
    
]