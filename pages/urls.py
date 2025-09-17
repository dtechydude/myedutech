from django.urls import path
from pages import views as page_views
from . import views

app_name ='pages'

urlpatterns = [

     path('', page_views.schoolly_home, name='schoolly-home'), 
     path('dashboard/', page_views.dashboard, name="portal-home"),
     path('home/', page_views.landing_page, name='landing-page'),
     path('help-center/', page_views.help_center, name='help-center'),
     path('support-info/', page_views.support_info, name='support_info'),
     path('lock-screen/', page_views.lock_screen, name='lock-screen'),
     path('bank-detail/', page_views.bank_detail, name='bank-detail'),
    #  path('record-result/', page_views.record_result, name='record-result'),
     path('success-submission/', page_views.success_submission, name='success_submission'),
     path('birthday-list/', page_views.birthday_list, name='birthday_list'),
     path('students-phone-list/', page_views.student_phone_list_view, name='students_phone_list'),
     path('students-email-list/', page_views.student_email_list_view, name='students_email_list'),

     path('teachers-phone-list/', page_views.teacher_guarantor_phone_list_view, name='teachers_phone_list'),
     path('teachers-email-list/', page_views.teacher_guarantor_email_list_view, name='teachers_email_list'),

     path('payment-instruction/', page_views.payment_instruction, name='payment_instruction'),
     path('payment-chart/', page_views.payment_chart, name='payment_chart'),
     path('video-guides/', page_views.video_guides_view, name='video-guides'),



     # path('<str:pk>/', views.StudentCardDetailView.as_view(), name='my_idcard'),

]
