# finance/api_urls.py
"""
Mount in your project's root urls.py, e.g.:

    path('api/finance/', include('finance.api_urls')),
"""
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register('bank-accounts', api_views.BankAccountViewSet, basename='api-bank-account')
router.register('fee-categories', api_views.FeeCategoryViewSet, basename='api-fee-category')
router.register('fee-structures', api_views.FeeStructureViewSet, basename='api-fee-structure')
router.register('invoices', api_views.InvoiceViewSet, basename='api-invoice')
router.register('payments', api_views.PaymentViewSet, basename='api-payment')
router.register('ledger', api_views.StudentLedgerViewSet, basename='api-ledger')
router.register('notifications', api_views.PaymentNotificationViewSet, basename='api-notification')
router.register('expense-categories', api_views.ExpenseCategoryViewSet, basename='api-expense-category')
router.register('vendors', api_views.VendorViewSet, basename='api-vendor')
router.register('expenses', api_views.ExpenseViewSet, basename='api-expense')

urlpatterns = router.urls
