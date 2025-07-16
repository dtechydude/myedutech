# your_project/urls.py (or payments/urls.py)

from django.contrib import admin
from django.urls import path, include
from payments import views as payment_views # Assuming your views are here
# If you created a new 'payments' app, it would be:
# from payments import views as payment_views

app_name = 'results'


urlpatterns = [
    # ... other paths ...

    # Payment URLs
    path('payments/make/', payment_views.make_payment, name='make_payment'),
    path('payments/history/', payment_views.payment_history, name='payment_history'),
    path('payments/receipt/<int:receipt_id>/', payment_views.view_receipt, name='view_receipt'),

    # New Report URLs
    path('payments/report/debtors/', payment_views.debtors_report, name='debtors_report'),
    path('payments/report/total/', payment_views.total_payments_report, name='total_payments_report'),

    # New AJAX endpoint for CategoryFee details
    path('api/get_category_fee_details/', payment_views.get_category_fee_details, name='get_category_fee_details'),

    # Example: If you have a base URL for your student management app
    # path('students/', include('student_management_app.urls')),
]

# If you have a dedicated 'payments' app, your project's urls.py might look like:
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('accounts/', include('django.contrib.auth.urls')), # For login/logout
#     path('payments/', include('payments.urls')), # Include your new payments app URLs
#     # ... other app URLs
# ]

# And in payments/urls.py:
# from django.urls import path
# from . import views
#
# urlpatterns = [
#     path('make/', views.make_payment, name='make_payment'),
#     path('history/', views.payment_history, name='payment_history'),
#     path('receipt/<int:receipt_id>/', views.view_receipt, name='view_receipt'),
#     path('report/debtors/', views.debtors_report, name='debtors_report'),
#     path('report/total/', views.total_payments_report, name='total_payments_report'),
#     path('api/get_category_fee_details/', views.get_category_fee_details, name='get_category_fee_details'),
# ]
