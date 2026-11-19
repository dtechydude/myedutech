from django.contrib import admin
from django.urls import path
from django.conf.urls import include
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.views.generic import TemplateView # For a simple placeholder home page



from django.contrib import admin
from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import path, include
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static                       # yours: used in urlpatterns += static(...)
from django.templatetags.static import static as static_url      # mine: renamed


def manifest(request):
    data = {
        "name": "KwikSchools",
        "short_name": "KwikSchools",
        "description": "Fast access to KwikSchools",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#ffffff",
        "theme_color": "#1d4ed8",
        "icons": [
            {"src": static_url("icons/icon-192.png"), "sizes": "192x192",
             "type": "image/png", "purpose": "any"},
            {"src": static_url("icons/icon-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "any"},
            {"src": static_url("icons/icon-maskable-512.png"), "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


class ServiceWorkerView(TemplateView):
    template_name = "sw.js"
    content_type = "application/javascript"

    def render_to_response(self, context, **kwargs):
        response = super().render_to_response(context, **kwargs)
        response["Service-Worker-Allowed"] = "/"
        response["Cache-Control"] = "no-cache"
        return response


urlpatterns = [
    # path("admin/", admin.site.urls),

    # PWA
    path("manifest.json", manifest, name="manifest"),
    path("sw.js", never_cache(ServiceWorkerView.as_view()), name="sw"),
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),

    # ... your existing urls
    # path("", include("yourapp.urls")),
# ]


# urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pages.urls', namespace='pages')),
    path('users/', include('users.urls')),
    path('students/', include('students.urls', namespace='students')), 
    path('staff/', include('staff.urls', namespace='staff')),
    path('results/', include('results.urls', namespace='results')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('attendance/', include('attendance.urls', namespace='attendance')),
    path('transport/', include('transport.urls', namespace='transport')),
    path('cbt/', include('cbt.urls', namespace='cbt')),
    path('curriculum/', include('curriculum.urls', namespace='curriculum')),
    path('tickets/', include('tickets.urls', namespace='tickets')),
    path('events/', include('events.urls', namespace='events')),
    path('prep_reports/', include('prep_reports.urls', namespace='prep_reports')),
    path('ai_center/', include('ai_center.urls', namespace='ai_center')),
    path('finance/', include('finance.urls', namespace='finance')),
    path('elearning/', include('elearning.urls', namespace='elearning')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('student-status/', include('studentstatus.urls')),
    # For Lesson Note
    path('lesson-notes/', include('elearning.lessonnotes.urls')),
    # for lesson notifications
    path('notifications/', include('elearning.notices.urls')),




       
    # Add this line below to fix the NoReverseMatch error
    path("ckeditor5/", include('django_ckeditor_5.urls'), name="ck_editor_5_upload_file"),


    # Placeholder for a home page (create templates/home.html)
    path('', TemplateView.as_view(template_name='home.html'), name='home'), 
    # This 'home' URL name is used in report_card_detail.html and StudentDashboardView fallback
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='some_general_dashboard_or_home_page'), # Fallback for unlinked users 

]


handler400 = "pages.error_views.bad_request"
handler403 = "pages.error_views.permission_denied"
handler404 = "pages.error_views.page_not_found"
handler500 = "pages.error_views.server_error"


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
