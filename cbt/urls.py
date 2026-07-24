# # from django.urls import path
# # from cbt import views as cbt_views

# # app_name ='cbt'

# # urlpatterns = [

# #      path('', cbt_views.cbt_home, name='cbt-home'),
# #      path('order/', cbt_views.cbt_order, name='cbt-order'),
# #      path('teacher/order/', cbt_views.cbt_teacher_order, name='cbt_teacher_order'),
# #      path('student/order/', cbt_views.student_cbt_home, name='cbt_student_home'),

# #      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),
# #      # URL for the CBT exam request form
# #      # path('request/', cbt_views.request_cbt_exam, name='request_exam'),
# #      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),

# #      #For Real CBT

# #      # 1. Existing Student Views
# # #     path('', cbt_views.quiz_list_view, name='main-view'),
    
# #     # 2. New Teacher Views (Placed before <pk> to avoid routing conflicts)
# #     path('cbt/', cbt_views.quiz_list_view, name='main-view'),
# #     path('teacher/add-quiz/', cbt_views.admin_add_quiz, name='teacher-quiz-add'),

# #     # Teacher sees list of quizzes
# #     path('teacher/add-question/', cbt_views.teacher_add_question, name='teacher-add-question'),

# #     # Teacher/admin clicks a specific quiz → add question form
# #     path('teacher/quiz/<int:quiz_id>/add-question/', cbt_views.teacher_add_question, name='teacher-add-question-quiz'),

# #     path('<pk>/', cbt_views.quiz_detail_view, name='quiz-view'),
# #     path('<pk>/data/', cbt_views.quiz_data_view, name='quiz-data-view'),
# #     path('<pk>/save/', cbt_views.save_quiz_view, name='save-view'),

# #     path('teacher/quiz/<int:quiz_id>/questions/', cbt_views.teacher_view_questions, name='teacher-view-questions'),
    
# #     path('teacher/results/', cbt_views.teacher_results_view, name='teacher-results-view'),
# #     path('results/export/csv/', cbt_views.export_results_csv, name='results-csv'),

# #     path('teacher/quiz/<int:quiz_id>/export/<str:export_type>/', cbt_views.export_questions,  name='export-questions'),

# #     path(
# #     'quiz/<int:quiz_id>/bulk-upload/',
# #     cbt_views.teacher_bulk_upload_questions,
# #     name='teacher-bulk-upload-questions',
# # ),

# # ]

# from django.urls import path
# from cbt import views as cbt_views

# app_name ='cbt'

# urlpatterns = [

#      path('', cbt_views.cbt_home, name='cbt-home'),
#      path('order/', cbt_views.cbt_order, name='cbt-order'),
#      path('teacher/order/', cbt_views.cbt_teacher_order, name='cbt_teacher_order'),
#      path('student/order/', cbt_views.student_cbt_home, name='cbt_student_home'),

#      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),
#      # URL for the CBT exam request form
#      # path('request/', cbt_views.request_cbt_exam, name='request_exam'),
#      path('request/submit/', cbt_views.submit_cbt_request, name='submit_request'),

#      #For Real CBT

#      # 1. Existing Student Views
# #     path('', cbt_views.quiz_list_view, name='main-view'),
    
#     # 2. New Teacher Views (Placed before <pk> to avoid routing conflicts)
#     path('cbt/', cbt_views.quiz_list_view, name='main-view'),
#     path('teacher/add-quiz/', cbt_views.admin_add_quiz, name='teacher-quiz-add'),

#     # Teacher sees list of quizzes
#     path('teacher/add-question/', cbt_views.teacher_add_question, name='teacher-add-question'),

#     # Teacher/admin clicks a specific quiz → add question form
#     path('teacher/quiz/<int:quiz_id>/add-question/', cbt_views.teacher_add_question, name='teacher-add-question-quiz'),

#     # ✅ NEW — Student result history (must stay ABOVE '<pk>/' below,
#     # otherwise Django would try to match "student" as a quiz pk).
#     path('student/results/', cbt_views.student_cbt_results_view, name='student-results-view'),

#     path('<pk>/', cbt_views.quiz_detail_view, name='quiz-view'),
#     path('<pk>/data/', cbt_views.quiz_data_view, name='quiz-data-view'),
#     path('<pk>/save/', cbt_views.save_quiz_view, name='save-view'),

#     path('teacher/quiz/<int:quiz_id>/questions/', cbt_views.teacher_view_questions, name='teacher-view-questions'),
    
#     path('teacher/results/', cbt_views.teacher_results_view, name='teacher-results-view'),
#     path('results/export/csv/', cbt_views.export_results_csv, name='results-csv'),

#     path('teacher/quiz/<int:quiz_id>/export/<str:export_type>/', cbt_views.export_questions,  name='export-questions'),

#     path(
#     'quiz/<int:quiz_id>/bulk-upload/',
#     cbt_views.teacher_bulk_upload_questions,
#     name='teacher-bulk-upload-questions',
# ),

# ]


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
    path('teacher/add-quiz/', cbt_views.admin_add_quiz, name='teacher-quiz-add'),

    # Teacher sees list of quizzes
    path('teacher/add-question/', cbt_views.teacher_add_question, name='teacher-add-question'),

    # Teacher/admin clicks a specific quiz → add question form
    path('teacher/quiz/<int:quiz_id>/add-question/', cbt_views.teacher_add_question, name='teacher-add-question-quiz'),

    # ✅ NEW — Student result history (must stay ABOVE '<pk>/' below,
    # otherwise Django would try to match "student" as a quiz pk).
    path('student/results/', cbt_views.student_cbt_results_view, name='student-results-view'),

    # ✅ NEW — Question Bank: browse & bulk-download past questions,
    # filterable by class/session/term/subject. Also above '<pk>/'.
    path('teacher/question-bank/', cbt_views.question_bank_view, name='question-bank-view'),
    path('teacher/question-bank/export/<str:export_type>/', cbt_views.export_question_bank, name='question-bank-export'),

    path('<pk>/', cbt_views.quiz_detail_view, name='quiz-view'),
    path('<pk>/data/', cbt_views.quiz_data_view, name='quiz-data-view'),
    path('<pk>/save/', cbt_views.save_quiz_view, name='save-view'),

    path('teacher/quiz/<int:quiz_id>/questions/', cbt_views.teacher_view_questions, name='teacher-view-questions'),
    
    path('teacher/results/', cbt_views.teacher_results_view, name='teacher-results-view'),
    path('results/export/csv/', cbt_views.export_results_csv, name='results-csv'),

    path('teacher/quiz/<int:quiz_id>/export/<str:export_type>/', cbt_views.export_questions,  name='export-questions'),

    path(
    'quiz/<int:quiz_id>/bulk-upload/',
    cbt_views.teacher_bulk_upload_questions,
    name='teacher-bulk-upload-questions',
),

]
