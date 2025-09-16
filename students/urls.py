from django.urls import path
from students import views as students_views
from students.views import StudentDetailView, StudentUpdateView, StudentDeleteView, StudentSelfDetailView, MyTeacherDetailView



app_name ='students'

urlpatterns = [

    path('student_list/', students_views.student_list, name='student-list'),
    path('parent-dashboard/', students_views.parent_dashboard, name='parent-dashboard'),
    path('parents/', students_views.parent_list_view, name='parent_list'),
    path('parents/export-csv/', students_views.export_parents_csv, name='export_parents_csv'),
    path('boarder_list/', students_views.student_boarder_list, name='boarder-list'),
    path('student_in_class/', students_views.student_in_class, name='student-in-class'),
    path('my-classmates/', students_views.my_classmates_view, name='my_classmates'),
    path('hostel_list/', students_views.hostel_list, name='hostel_list'),
    path('graduated_students_list/', students_views.graduated_students_list, name='graduated_students_list'),
    path('graduate-students/', students_views.graduate_students_view, name='graduate_students'),
    path('upcoming_birthdays/', students_views.upcoming_birthdays_view, name='upcoming_birthdays'),



    path('student/id-card/<int:student_id>/', students_views.StudentIDCardView.as_view(), name='student_id_card'),
    path('promote-students/', students_views.promote_students_view, name='promote_students'),
    path('promote-individual-students/', students_views.promote_individual_students_view, name='promote_individual_students'),
    path('assign-classgroup-to-students/', students_views.assign_classgroup_to_students_view, name='assign_classgroup_to_students'),




    # path('create-student-profile/', views.create_student_profile, name='create_student_profile'), # Example

    # Search student detail app
    path('search/', students_views.search, name='search'),
    path('student_search_list/', students_views.student_search_list, name='student_search_list'),
    
    path('my-detail/', StudentSelfDetailView.as_view(), name="student-self-detail"),

    path('<str:id>/', StudentDetailView.as_view(), name="student-detail"),
    path('students/<str:usn>/update/', StudentUpdateView.as_view(), name='student-update'),

    # path('<str:id>/update/', StudentUpdateView.as_view(), name="student-update"),
    path('<str:id>/delete/', StudentDeleteView.as_view(), name="student-delete"), 
    path('<str:id>/', MyTeacherDetailView.as_view(), name="my-teacher-detail"),


         
]