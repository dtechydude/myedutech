from django.urls import path
from cbt import views as cbt_views

app_name ='cbt'

urlpatterns = [

     path('', cbt_views.cbt_home, name='cbt-home'),
     path('order/', cbt_views.cbt_order, name='cbt-order'),
     path('teacher/order/', cbt_views.cbt_teacher_order, name='cbt_teacher_order'),
     path('student/order/', cbt_views.student_cbt_home, name='cbt_student_home'),

     path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),
     # URL for the CBT exam request form
     # path('request/', cbt_views.request_cbt_exam, name='request_exam'),
     path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),

     #For Real CBT

     # 1. Existing Student Views
#     path('', cbt_views.quiz_list_view, name='main-view'),
    
    # 2. New Teacher Views (Placed before <pk> to avoid routing conflicts)
    path('cbt/', cbt_views.quiz_list_view, name='main-view'),
    path('teacher/add-quiz/', cbt_views.teacher_add_quiz, name='teacher-quiz-add'),
    path('teacher/quiz/<int:quiz_id>/add-question/', cbt_views.teacher_add_question, name='teacher-add-question'),
    path('<pk>/', cbt_views.quiz_detail_view, name='quiz-view'),
    path('<pk>/data/', cbt_views.quiz_data_view, name='quiz-data-view'),
    path('<pk>/save/', cbt_views.save_quiz_view, name='save-view'),

    path('teacher/quiz/<int:quiz_id>/questions/', cbt_views.teacher_view_questions, name='teacher-view-questions'),
    path('teacher/results/', cbt_views.teacher_results_view, name='teacher-results-view'),

]
