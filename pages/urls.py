from django.urls import path
from pages import views as page_views
from . import views

app_name ='pages'

urlpatterns = [

     path('', page_views.schoolly_home, name='schoolly-home'), 
     path('dashboard/', page_views.dashboard, name="portal-home"),
     path('help-center/', page_views.help_center, name='help-center'),
     path('support-info/', page_views.support_info, name='support_info'),
     path('lock-screen/', page_views.lock_screen, name='lock-screen'),
    #  path('record-result/', page_views.record_result, name='record-result'),
    #  path('success-submission/', page_views.success_submission, name='success_submission'),
     path('birthday-list/', page_views.birthday_list, name='birthday_list'),
     path('phone-list/', page_views.phone_list, name='phone_list'),
     path('email-list/', page_views.email_list, name='email_list'),


     # path('<str:pk>/', views.StudentCardDetailView.as_view(), name='my_idcard'),

]
