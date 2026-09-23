from django.urls import path

from . import views

app_name = 'studentstatus'

urlpatterns = [
    path('list/', views.StudentStatusListView.as_view(), name='list'),
    path('log/', views.StatusLogListView.as_view(), name='log'),
    path('<int:pk>/', views.StudentStatusChangeView.as_view(), name='change'),
]