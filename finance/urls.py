# finance/urls.py
from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    # --- Dashboard ---
    path('', views.dashboard, name='dashboard'),

    # --- Fee Categories ---
    path('fee-categories/', views.FeeCategoryListView.as_view(), name='fee_category_list'),
    path('fee-categories/add/', views.FeeCategoryCreateView.as_view(), name='fee_category_add'),
    path('fee-categories/<int:pk>/edit/', views.FeeCategoryUpdateView.as_view(), name='fee_category_edit'),

    # --- Fee Structure (class/term/session fee setup) ---
    path('fee-structure/', views.FeeStructureListView.as_view(), name='fee_structure_list'),
    path('fee-structure/add/', views.FeeStructureCreateView.as_view(), name='fee_structure_add'),
    path('fee-structure/<int:pk>/edit/', views.FeeStructureUpdateView.as_view(), name='fee_structure_edit'),
    path('fee-structure/<int:pk>/delete/', views.FeeStructureDeleteView.as_view(), name='fee_structure_delete'),

    # --- Student Discounts / Concessions (sibling, staff-ward, scholarship, etc.) ---
    path('discounts/', views.StudentDiscountListView.as_view(), name='discount_list'),
    path('discounts/add/', views.StudentDiscountCreateView.as_view(), name='discount_add'),
    path('discounts/<int:pk>/edit/', views.StudentDiscountUpdateView.as_view(), name='discount_edit'),
    path('discounts/<int:pk>/deactivate/', views.deactivate_discount, name='discount_deactivate'),

    # --- Student Fee Exceptions (per-student exclude/include of a class-wide fee) ---
    path('fee-exceptions/', views.StudentFeeExceptionListView.as_view(), name='fee_exception_list'),
    path('fee-exceptions/add/', views.StudentFeeExceptionCreateView.as_view(), name='fee_exception_add'),
    path('fee-exceptions/<int:pk>/delete/', views.delete_fee_exception, name='fee_exception_delete'),

    # --- Printable / Exportable Fee Table ---
    path('fee-table/', views.fee_table, name='fee_table'),
    path('fee-table/pdf/', views.fee_table_pdf, name='fee_table_pdf'),

    # --- Bank Accounts ---
    path('bank-accounts/', views.BankAccountListView.as_view(), name='bank_account_list'),
    path('bank-accounts/add/', views.BankAccountCreateView.as_view(), name='bank_account_add'),
    path('bank-accounts/<int:pk>/edit/', views.BankAccountUpdateView.as_view(), name='bank_account_edit'),

    # --- Invoices ---
    path('invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/add/', views.invoice_create, name='invoice_create'),
    path('invoices/generate/', views.generate_invoices, name='generate_invoices'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('invoices/<int:pk>/items/', views.invoice_edit_items, name='invoice_edit_items'),
    path('invoices/<int:invoice_pk>/installments/', views.manage_installment_plan, name='manage_installment_plan'),
    path('invoices/<int:invoice_pk>/installments/delete/', views.delete_installment_plan,
         name='delete_installment_plan'),

    # --- Payments ---
    path('payments/', views.PaymentListView.as_view(), name='payment_list'),
    path('payments/directory/', views.student_payment_directory, name='payment_directory'),
    path('payments/make/', views.make_payment, name='make_payment'),
    path('payments/parent/make/', views.make_parent_payment, name='make_parent_payment'),

    # --- Receipts ---
    path('receipts/<int:pk>/', views.receipt_detail, name='receipt_detail'),
    path('receipts/<int:pk>/pdf/', views.receipt_pdf, name='receipt_pdf'),

    # --- Payment Notifications ---
    path('notify-payment/', views.notify_payment, name='notify_payment'),
    path('notify-payment/success/', views.payment_notification_success, name='payment_notification_success'),
    path('notifications/', views.PaymentNotificationListView.as_view(), name='notification_list'),
    path('notifications/mine/', views.UserPaymentNotificationListView.as_view(), name='my_notifications'),
    path('notifications/<int:pk>/process/', views.process_notification, name='process_notification'),

    # --- Reports ---
    path('reports/debtors/', views.debtors_report, name='debtors_report'),
    path('ledgers/resync/', views.resync_ledgers, name='resync_ledgers'),
    path('reports/total-payments/', views.total_payments_report, name='total_payments_report'),
    path('reports/profit-and-loss/', views.profit_loss_report, name='profit_loss_report'),

    # --- Expenses ---
    path('expenses/', views.ExpenseListView.as_view(), name='expense_list'),
    path('expenses/add/', views.ExpenseCreateView.as_view(), name='expense_add'),
    path('expenses/<int:pk>/edit/', views.ExpenseUpdateView.as_view(), name='expense_edit'),
    path('expenses/<int:pk>/delete/', views.ExpenseDeleteView.as_view(), name='expense_delete'),
    path('expenses/<int:pk>/approve/', views.approve_expense, name='expense_approve'),
    path('expense-categories/', views.ExpenseCategoryListView.as_view(), name='expense_category_list'),
    path('expense-categories/add/', views.ExpenseCategoryCreateView.as_view(), name='expense_category_add'),
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/add/', views.VendorCreateView.as_view(), name='vendor_add'),

    # --- AJAX ---
    path('ajax/student-search/', views.student_search_ajax, name='student_search_ajax'),
    path('ajax/student/<int:student_id>/invoices/', views.student_invoices_ajax, name='student_invoices_ajax'),
]
