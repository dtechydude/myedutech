
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


]
