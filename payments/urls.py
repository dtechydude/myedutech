# your_project/urls.py (or payments/urls.py)

from django.contrib import admin
from django.urls import path, include
from payments import views as payment_views # Assuming your views are here
# If you created a new 'payments' app, it would be:
# from payments import views as payment_views

app_name = 'payments'


urlpatterns = [
    # ... other paths ...

    # Payment URLs
    path('payments/make/', payment_views.make_payment, name='make_payment'),
    path('payments/history/', payment_views.payment_history, name='payment_history'),
    path('payments/receipt/<int:receipt_id>/', payment_views.view_receipt, name='view_receipt'),
    path('category_fee/', payment_views.payment_chart_list, name='payment_chart_list'),

    # New Report URLs
    path('payments/report/debtors/', payment_views.debtors_report, name='debtors_report'),
    path('payments/report/total/', payment_views.total_payments_report, name='total_payments_report'),

    path('debtors-report/pdf/', payment_views.debtors_report_pdf, name='debtors_report_pdf'),
    # This is the line that needs to be absolutely correct:
    path('debtors-report/csv/', payment_views.debtors_report_csv, name='debtors_report_csv'), # <-- ENSURE name='debtors_report_csv' matches exactly
    
    # Route For getting summary for term
    path('finance-dashboard/', payment_views.FinanceDashboardView.as_view(), name='finance_dashboard'),

    # New AJAX endpoint for CategoryFee details
    path('api/get_category_fee_details/', payment_views.get_category_fee_details, name='get_category_fee_details'),

    path('total-payments-report/pdf/', payment_views.total_payments_report_pdf, name='total_payments_report_pdf'), # New PDF for Total Payments Report
    path('total-payments-report/csv/', payment_views.total_payments_report_csv, name='total_payments_report_csv'), # New CSV for Total Payments Report

    # Example: If you have a base URL for your student management app
    # path('students/', include('student_management_app.urls')),
]

