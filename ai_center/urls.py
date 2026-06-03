from django.urls import path
# from .views import ai_center_dashboard, ai_usage_guide
from ai_center import views as ai_views

app_name = 'ai_center'

urlpatterns = [

    path('', ai_views.ai_center_dashboard, name='ai_center_dashboard'),


    path("guide/", ai_views.ai_usage_guide, name="guide"),

 ]