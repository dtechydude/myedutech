from django.urls import path
from staff import views as staff_views
from .views import(TeacherDetailView,
                   TeacherUpdateView,TeacherDeleteView,
                     TeacherSelfDetailView, TeacherStudentCountListView)


app_name ='staff'

urlpatterns = [

    path('teacher_list/', staff_views.teachers_list, name='teacher-list'),
    path('assignments/', staff_views.teacher_subjects_standards_view, name='teacher_assignments'),
    path('<int:teacher_id>/profile/', staff_views.teacher_profile_view, name='teacher_profile'),
    path('my-assignments/', staff_views.my_assignments_view, name='my_assignments'),
    path('assign-form-teacher/', staff_views.assign_form_teacher_view, name='assign_form_teacher'),
    path('assign-form-teacher-to-classgroup/', staff_views.assign_form_teacher_to_classgroup_view, name='assign_form_teacher_to_classgroup'),

    path('teacher/signup/user/', staff_views.teacher_user_signup, name='teacher_user_signup'),
    path('teacher/signup/details/', staff_views.teacher_details_signup, name='teacher_details_signup'),
    path('teacher/signup/success/', staff_views.teacher_signup_success, name='teacher_signup_success'),

    path('my_teacher_view/', staff_views.my_teacher_view, name='my_teacher_view'),
    
    path('classroom/<str:class_id>/students/', staff_views.classroom_students, name='classroom_students'),

    #  path('staff-my-detail/', StaffSelfDetailView.as_view(), name="staff-self-detail"),
    path('teacher-my-detail/', TeacherSelfDetailView.as_view(), name="teacher-self-detail"),

    path('<str:id>/', TeacherDetailView.as_view(), name="teacher-detail"),
    path('<str:id>/update/', TeacherUpdateView.as_view(), name="teacher-update"),
    path('<str:id>/delete/', TeacherDeleteView.as_view(), name="teacher-delete"),

    

     # Teacher's Own Student List
    # path('teacher/<int:assign_id>/Students/attendance/', staff_views.my_student, name='my_student'),
    path('teacher/<slug:teacher_id>/<int:choice>/Classes/', staff_views.my_clas, name='my_clas'),

     # URL to list all teachers and their student counts (class-based)
    path('teachers/cbv_all_counts/', TeacherStudentCountListView.as_view(), name='cbv_all_teachers_student_counts'),
    
     

]