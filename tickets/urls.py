# tickets/urls.py
from django.urls import path
from . import views

app_name = 'tickets'
urlpatterns = [
    # Student views
    path('new/', views.create_ticket, name='create_ticket'),
    path('', views.ticket_list, name='ticket_list'),
    path('<int:pk>/', views.ticket_detail, name='ticket_detail'),
    
    # Admin views
    path('admin/', views.admin_ticket_list, name='admin_ticket_list'),
    path('admin/<int:pk>/', views.admin_ticket_detail, name='admin_ticket_detail'),
    path('admin/broadcast/create/', views.broadcast_ticket_create, name='broadcast_ticket_create'),

]