from django.urls import path

from .views import ai_center_dashboard

app_name = 'ai_center'

urlpatterns = [

    path(
        '',
        ai_center_dashboard,
        name='ai_center_dashboard'
    ),

 ]