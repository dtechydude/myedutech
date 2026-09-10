from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('inventory', views.InventoryDashboardView.as_view(), name='dashboard'),
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('items/add/', views.ItemCreateView.as_view(), name='item_add'),
    path('items/<int:pk>/edit/', views.ItemUpdateView.as_view(), name='item_edit'),
    path('movements/add/', views.StockMovementCreateView.as_view(), name='movement_add'),
    path('movements/', views.MovementListView.as_view(), name='movement_list'),

    path('items/<int:pk>/detail/', views.ItemDetailView.as_view(), name='item_detail'),
    path('items/<int:pk>/qr/', views.item_qr_label, name='item_qr_label'),
    path('scan/<uuid:qr_uid>/', views.ScanDetailView.as_view(), name='scan_detail'),
    path('items/<int:pk>/issue/', views.IssueItemView.as_view(), name='item_issue'),
    path('custody/<int:pk>/return/', views.ReturnItemView.as_view(), name='item_return'),
    path('custody/', views.CustodyListView.as_view(), name='custody_list'),
    path('items/qr-print/', views.BulkQRPrintView.as_view(), name='bulk_qr_print'),
]