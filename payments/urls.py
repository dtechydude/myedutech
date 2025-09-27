# payments/urls.py

from django.urls import path
from . import views as payment_views
from payments.views import PaymentNotificationListView

app_name = 'payments'

urlpatterns = [
    # --- Core Payment Processing ---
    path('make-payment/', payment_views.make_payment, name='make_payment'),
    path('payment/<int:pk>/', payment_views.payment_detail, name='payment-detail'),
    path('notify-payment/', payment_views.notify_payment, name='notify_payment'),
    path('notification-success/', payment_views.payment_notification_success, name='payment-notification-success'),
    # NEW STAFF PATHS
    path('notifications/list/', PaymentNotificationListView.as_view(), name='notification-list'),
    path('notifications/process/<int:pk>/', payment_views.process_notification, name='process-notification'),

    path('parent/make-payment/', payment_views.make_parent_payment, name='make_parent_payment'),
    path('make-full-payment/<int:student_id>/<int:session_id>/<int:term_id>/', payment_views.make_full_payment, name='make_full_payment'),

    path('payment-chart-list/', payment_views.payment_chart_list, name='payment_chart_list'),
    path('get-category-fee-details/', payment_views.get_category_fee_details, name='get_category_fee_details'),
     # This URL is for AJAX requests to get a student's balance
    path('get-student-balance/<int:student_id>/', payment_views.get_student_balance_api, name='get_student_balance'),


    # --- Financial Reports & Dashboards ---
    path('dashboard/', payment_views.finance_dashboard, name='finance_dashboard'),
    path('summary/', payment_views.payment_summary, name='payment_summary'),
    path('debtors/', payment_views.debtors_report, name='debtors_report'),
    path('total-payments/', payment_views.total_payments_report, name='total_payments_report'),

    # --- Report Exports ---
    path('debtors/pdf/', payment_views.debtors_report_pdf, name='debtors_report_pdf'),
    path('debtors/csv/', payment_views.debtors_report_csv, name='debtors_report_csv'),
    path('total-payments/pdf/', payment_views.total_payments_report_pdf, name='total_payments_report_pdf'),
    path('total-payments/csv/', payment_views.total_payments_report_csv, name='total_payments_report_csv'),

    # --- Student & Parent Specific ---
    path('history/', payment_views.payment_history, name='payment_history'),
    path('invoice/<int:student_id>/', payment_views.student_invoice, name='student_invoice'),
    path('my-invoice/', payment_views.student_invoice_view, name='student_invoice'),


    # --- Receipts ---
    path('receipt/<int:receipt_pk>/', payment_views.payment_receipt, name='payment_receipt'),
    # The old 'view_receipt' path is removed as it's no longer needed.
    path('receipt/<int:receipt_id>/pdf/', payment_views.receipt_pdf, name='receipt_pdf'),

    ## --- API Endpoints ---
    #path('api/get-fees/<int:student_id>/', payment_views.get_student_fees_api, name='get_student_fees_api'),
    
    # New API endpoint for getting total student balance
    path('api/get-balance/<int:student_id>/', payment_views.get_student_balance_api, name='get_student_balance_api'),

    path('student-search-ajax/', payment_views.student_search_ajax, name='student_search_ajax'),

]