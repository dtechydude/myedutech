from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import StudentOnRoute, BusPayment, Route
from .resources import StudentOnRouteResource, BusPaymentResource
from django.db.models import Sum



class RouteAdmin(ImportExportModelAdmin):
    list_display = ('name', 'route_id', 'bus_fee', 'direction', 'staff_in_charge', 'driver', 'driver_phone')
    search_fields = ('name', 'staff_in_charge__first_name',)
    ordering = ['name',]
    raw_id_fields = ['staff_in_charge']
    exclude = ('slug',)



# Use this inline to display payments on the StudentOnRoute admin page
class BusPaymentInline(admin.TabularInline):
    model = BusPayment
    extra = 1
    fields = ('amount_paid', 'payment_method', 'is_approved')
    readonly_fields = ('payment_date',)

@admin.register(StudentOnRoute)
class StudentOnRouteAdmin(ImportExportModelAdmin):
    resource_class = StudentOnRouteResource
    list_display = (
        'student',
        'route',
        'session',
        'term',
        'is_active',
        'total_paid_display',
        'balance_display',
    )
    list_filter = (
        'route',
        'session',
        'term',
        'is_active',
    )
    search_fields = (
        'student__user__username',
        'student__full_name',
        'route__name',
    )
    list_editable = (
        'is_active',
    )
    readonly_fields = (
        'total_paid_display',
        'balance_display',
    )
    raw_id_fields = ['student',]

    inlines = [BusPaymentInline]
    actions = ['mark_as_active', 'mark_as_inactive']

    def total_paid_display(self, obj):
        total = obj.payments.filter(is_approved=True).aggregate(sum_amount=Sum('amount_paid'))['sum_amount']
        return f'N{total:,.2f}' if total is not None else 'N0.00'
    total_paid_display.short_description = 'Amount Paid'

    def balance_display(self, obj):
        total_paid = obj.payments.filter(is_approved=True).aggregate(sum_amount=Sum('amount_paid'))['sum_amount'] or 0
        balance = obj.route.bus_fee - total_paid
        if balance > 0:
            return f'N{balance:,.2f}'
        return f'-N{abs(balance):,.2f}' if balance < 0 else 'N0.00'
    balance_display.short_description = 'Balance'
    
    @admin.action(description="Mark selected students as active on bus")
    def mark_as_active(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} students were marked as active on bus.")

    @admin.action(description="Mark selected students as inactive on bus")
    def mark_as_inactive(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} students were marked as inactive on bus.")

@admin.register(BusPayment)
class BusPaymentAdmin(ImportExportModelAdmin):
    resource_class = BusPaymentResource
    list_display = (
        'enrollment',
        'amount_paid',
        'payment_method',
        'payment_date',
        'is_approved',
    )
    list_filter = (
        'is_approved',
        'payment_method',
        'payment_date',
    )
    search_fields = (
        'enrollment__student__user__username',
        'enrollment__route__name',
        'enrollment__student__full_name',
    )
    list_editable = (
        'is_approved',
    )

    actions = ['approve_payments']

    @admin.action(description="Approve selected payments")
    def approve_payments(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} payments were approved.") 



admin.site.register(Route, RouteAdmin)
# admin.site.register(StudentOnRoute, StudentOnRouteAdmin)
