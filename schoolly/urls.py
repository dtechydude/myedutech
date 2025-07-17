from django.contrib import admin
from django.urls import path
from django.conf.urls import include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.views.generic import TemplateView # For a simple placeholder home page




urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls', namespace='pages')),
    path('users/', include('users.urls', namespace='users')),
    path('students/', include('students.urls', namespace='students')), 
    path('staff/', include('staff.urls', namespace='staff')),
    path('results/', include('results.urls', namespace='results')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('attendance/', include('attendance.urls', namespace='attendance')),
    path('transport/', include('transport.urls', namespace='transport')),
    path('cbt/', include('cbt.urls', namespace='cbt')),
    path('curriculum/', include('curriculum.urls', namespace='curriculum')),
       


    # Placeholder for a home page (create templates/home.html)
    path('', TemplateView.as_view(template_name='home.html'), name='home'), 
    # This 'home' URL name is used in report_card_detail.html and StudentDashboardView fallback
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='some_general_dashboard_or_home_page'), # Fallback for unlinked users 

]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
