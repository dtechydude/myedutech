from django.urls import path
from . import views



app_name = 'events'

urlpatterns = [
    path('', views.CalendarView.as_view(), name='calendar'),
    path('new/', views.EventFormView.as_view(), name='event_new'),
    path('edit/<int:pk>/', views.EventUpdateView.as_view(), name='event_edit'),
    path('delete/<int:pk>/', views.EventDeleteView.as_view(), name='event_delete'),
    path('deleted/', views.EventDeleteSuccessView.as_view(), name='event_delete_success'),
    path('<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
]