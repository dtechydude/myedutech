# from django.urls import path
# from attendance import views as attendance_views




# app_name ='attendance'

# urlpatterns = [
#     # path('', views.att_index, name='att_index'),
# #     path('teacher/', views.index, name='index'),
# #
# # My Attendance Logic
#     path('teacher/dashboard/', attendance_views.teacher_dashboard, name='teacher_dashboard'),
#     path('teacher/attendance/<int:standard_id>/', attendance_views.mark_attendance, name='mark_attendance'),
#     path('teacher/attendance/success/<int:standard_id>/', attendance_views.attendance_success, name='attendance_success'),
#     path('report/', attendance_views.attendance_report, name='attendance_report'),
#     path('students/', attendance_views.student_list, name='student_list'),
#     path('students/<str:USN>/attendance-summary/', attendance_views.student_attendance_summary, name='student_attendance_summary'),


# ]




from django.urls import path
from . import views


app_name ='attendance'

urlpatterns = [
    path('take-attendance/', views.take_daily_attendance, name='take_daily_attendance'),
    path('attendance-report/', views.attendance_report, name='attendance_report'),
    # path('attendance-success/', views.attendance_success, name='attendance_success'), # If you still want a separate success page
]