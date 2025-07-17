
from django.urls import path
from cbt import views as cbt_views

app_name ='cbt'

urlpatterns = [

     path('', cbt_views.cbt_home, name='cbt-home'),

]
