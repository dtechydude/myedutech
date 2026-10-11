from django.urls import path

from . import views

# Mount in the PROJECT urls.py:
#     path('notifications/', include('elearning.notices.urls')),
app_name = 'notices'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('read-all/', views.MarkAllReadView.as_view(), name='read_all'),
    path('<int:pk>/open/', views.NotificationOpenView.as_view(), name='open'),
    path('<int:pk>/read/', views.MarkReadView.as_view(), name='read'),
]