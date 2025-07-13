from django.urls import path
from students import views as students_views
from students.views import StudentDetailView, StudentUpdateView, StudentDeleteView, StudentSelfDetailView, MyTeacherDetailView



app_name ='students'

urlpatterns = [

    path('student_list/', students_views.student_list, name='student-list'),
    path('boarder_list/', students_views.student_boarder_list, name='boarder-list'),
    path('student_in_class/', students_views.student_in_class, name='student-in-class'),
    path('my-classmates/', students_views.my_classmates_view, name='my_classmates'),
    path('hostel_list/', students_views.hostel_list, name='hostel_list'),
    # path('create-student-profile/', views.create_student_profile, name='create_student_profile'), # Example

    # Search student detail app
    path('search/', students_views.search, name='search'),
    path('student_search_list/', students_views.student_search_list, name='student_search_list'),
    
    path('my-detail/', StudentSelfDetailView.as_view(), name="student-self-detail"),

    path('<str:id>/', StudentDetailView.as_view(), name="student-detail"),
    path('<str:id>/update/', StudentUpdateView.as_view(), name="student-update"),
    path('<str:id>/delete/', StudentDeleteView.as_view(), name="student-delete"), 
    path('<str:id>/', MyTeacherDetailView.as_view(), name="my-teacher-detail"),

    #  # Search student detail app
    # path('student_search/', students_views.search_form, name='search_form'),
    # path('search-studen-result/', students_views.search_students, name='student-search-result'),
     

    #render id card as pdf
    path('idcard-pdf/<pk>/', students_views.id_render_pdf_view, name="idcard-pdf-view"),
    #path('idcard/', PDFTemplateView.as_view(template_name='students/student_id_card.html',
    #                                       filename='id_card.pdf'), name='id-card-pdf'),


     
]