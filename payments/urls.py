# your_project/urls.py (or payments/urls.py)

from django.contrib import admin
from django.urls import path, include
from payments import views as payment_views # Assuming your views are here
# If you created a new 'payments' app, it would be:
# from payments import views as payment_views

app_name = 'payments'


urlpatterns = [
    # ... other paths ...

    # Payment Processing URLs
    path('payments/make/', payment_views.make_payment, name='make_payment'),
    path('make-individual-payment/', payment_views.make_individual_payment, name='individual-payment'),
    path('make-group-payment/', payment_views.make_group_payment, name='group-payment'),
    path('make-payment/<int:student_id>/', payment_views.make_payment_for_child, name='make-payment-for-child'),
    
    # History and Details URLs
    path('payments/history/', payment_views.payment_history, name='payment_history'),
    path('payments/details/<int:pk>/<int:category_pk>/<int:term_pk>/<int:session_pk>/', payment_views.payment_details, name='payment-details'),
    path('payments/receipt/<int:receipt_id>/', payment_views.view_receipt, name='receipt'),
    
    # Chart and Report URLs
    path('category_fee/', payment_views.payment_chart_list, name='payment_chart_list'),
    path('archived-fees-chart/', payment_views.archive_payment_chart_list, name='archive_payment_chart_list'),
    path('generate-fees/', payment_views.generate_student_fees, name='generate_student_fees'),
    path('payments/report/debtors/', payment_views.debtors_report, name='debtors_report'),
    path('payments/report/total/', payment_views.total_payments_report, name='total_payments_report'),
    path('debtors-report/pdf/', payment_views.debtors_report_pdf, name='debtors_report_pdf'),
    path('debtors-report/csv/', payment_views.debtors_report_csv, name='debtors_report_csv'),
    path('finance-dashboard/', payment_views.FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('finance-dashboard-chartview/', payment_views.finance_dashboard, name='finance_dashboard_chartview'),
    path('api/get_category_fee_details/', payment_views.get_category_fee_details, name='get_category_fee_details'),
    path('total-payments-report/pdf/', payment_views.total_payments_report_pdf, name='total_payments_report_pdf'),
    path('total-payments-report/csv/', payment_views.total_payments_report_csv, name='total_payments_report_csv'),
]
