from django.contrib import admin
from .models import InventoryCategory, InventoryItem, StockMovement


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# @admin.register(Vendor)
# class VendorAdmin(admin.ModelAdmin):
#     list_display = ('name', 'phone')
#     search_fields = ('name',)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity_in_stock', 'unit', 'reorder_level', 'total_value', 'is_asset', 'quantity_in_stock', 'low_stock_flag')
    list_filter = ('category', 'unit', 'is_asset')
    search_fields = ('name', 'location')
    # readonly_fields = ('quantity_in_stock', 'qr_uid')
    readonly_fields = ('qr_uid',)

    @admin.display(description='Status', boolean=True)
    def low_stock_flag(self, obj):
        return obj.is_low_stock


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'movement_type', 'quantity', 'issued_to', 'vendor', 'date', 'recorded_by')
    list_filter = ('movement_type', 'date')
    search_fields = ('item__name', 'issued_to')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


from .models import ItemCustody


@admin.register(ItemCustody)
class ItemCustodyAdmin(admin.ModelAdmin):
    list_display = ('item', 'held_by_name', 'issued_date', 'expected_return_date', 'returned_date', 'status_flag')
    list_filter = ('issued_date', 'returned_date')
    search_fields = ('item__name', 'held_by_name')
    readonly_fields = ('issued_by', 'received_by')

    @admin.display(description='Status')
    def status_flag(self, obj):
        if obj.returned_date:
            return "Returned"
        return "OVERDUE" if obj.is_overdue else "With Holder"