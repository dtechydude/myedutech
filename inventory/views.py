from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.urls import reverse_lazy
from django.db.models import Sum, F, Q
from .models import InventoryItem, StockMovement, InventoryCategory
from finance.models import Vendor


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_active and (self.request.user.is_staff or self.request.user.is_superuser)


class InventoryDashboardView(LoginRequiredMixin, StaffOnlyMixin, TemplateView):
    template_name = 'inventory/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items = InventoryItem.objects.select_related('category')

        ctx['total_items'] = items.count()
        ctx['total_stock_value'] = sum(i.total_value for i in items)
        ctx['low_stock_items'] = [i for i in items if i.is_low_stock]
        ctx['recent_movements'] = StockMovement.objects.select_related('item', 'vendor').order_by('-date')[:10]
        return ctx


class ItemListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    model = InventoryItem
    template_name = 'inventory/item_list.html'
    context_object_name = 'items'
    paginate_by = 25

    def get_queryset(self):
        qs = InventoryItem.objects.select_related('category')
        q = self.request.GET.get('q')
        category = self.request.GET.get('category')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = InventoryCategory.objects.all()
        return ctx


from django import forms

class ItemCreateView(LoginRequiredMixin, StaffOnlyMixin, CreateView):
    model = InventoryItem
    fields = ['name', 'category', 'unit', 'reorder_level', 'unit_cost', 'location']
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory:item_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()
        return form


class ItemUpdateView(LoginRequiredMixin, StaffOnlyMixin, UpdateView):
    model = InventoryItem
    fields = ['name', 'category', 'unit', 'reorder_level', 'unit_cost', 'location']
    template_name = 'inventory/item_form.html'
    success_url = reverse_lazy('inventory:item_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} form-control'.strip()
        return form



class StockMovementCreateView(LoginRequiredMixin, StaffOnlyMixin, CreateView):
    model = StockMovement
    fields = ['item', 'movement_type', 'quantity', 'vendor', 'issued_to', 'to_location', 'notes']
    template_name = 'inventory/movement_form.html'
    success_url = reverse_lazy('inventory:movement_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for name, field in form.fields.items():
            existing = field.widget.attrs.get('class', '')
            base_class = 'form-select' if name in ('item', 'movement_type', 'vendor') else 'form-control'
            field.widget.attrs['class'] = f'{existing} {base_class}'.strip()
            if name == 'notes':
                field.widget.attrs['rows'] = 3
        return form

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)




class MovementListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    model = StockMovement
    template_name = 'inventory/movement_list.html'
    context_object_name = 'movements'
    paginate_by = 30

    def get_queryset(self):
        return StockMovement.objects.select_related('item', 'vendor', 'recorded_by').order_by('-date')


from django.views.generic import DetailView, View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from .models import ItemCustody


class ItemDetailView(LoginRequiredMixin, StaffOnlyMixin, DetailView):
    model = InventoryItem
    template_name = 'inventory/item_detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['custody_history'] = self.object.custody_records.select_related(
            'held_by_user', 'issued_by', 'received_by'
        )
        return ctx


def item_qr_label(request, pk):
    """
    Printable QR label for a single item. Uses the same qrcodejs pattern
    already used across ID cards / receipts (self-hosted, no new package).
    """
    item = get_object_or_404(InventoryItem, pk=pk)
    scan_url = request.build_absolute_uri(item.get_qr_scan_url())
    return render(request, 'inventory/item_qr_label.html', {'item': item, 'scan_url': scan_url})


class ScanDetailView(DetailView):
    """
    Public-facing page opened when someone scans the printed QR code.
    Deliberately login-agnostic (no LoginRequiredMixin) so any staff
    member with a phone camera can scan and immediately see what the
    item is and who currently has it — the whole point of the QR label.
    Does NOT expose edit/issue actions unless the viewer is staff.
    """
    model = InventoryItem
    template_name = 'inventory/scan_detail.html'
    context_object_name = 'item'
    slug_field = 'qr_uid'
    slug_url_kwarg = 'qr_uid'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_custody'] = self.object.current_custody
        return ctx


class IssueItemView(LoginRequiredMixin, StaffOnlyMixin, View):
    def get(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)
        if item.current_custody:
            messages.warning(request, f'{item.name} is already issued to {item.current_custody.held_by_name}. Process a return first.')
            return redirect('inventory:item_detail', pk=item.pk)
        return render(request, 'inventory/item_issue_form.html', {'item': item})

    def post(self, request, pk):
        item = get_object_or_404(InventoryItem, pk=pk)
        held_by_name = request.POST.get('held_by_name', '').strip()
        expected_return_date = request.POST.get('expected_return_date') or None
        issue_notes = request.POST.get('issue_notes', '').strip()

        if not held_by_name:
            messages.error(request, 'Please enter who this item is being issued to.')
            return render(request, 'inventory/item_issue_form.html', {'item': item})

        ItemCustody.objects.create(
            item=item,
            held_by_name=held_by_name,
            expected_return_date=expected_return_date,
            issue_notes=issue_notes,
            issued_by=request.user,
        )
        messages.success(request, f'{item.name} has been issued to {held_by_name}.')
        return redirect('inventory:item_detail', pk=item.pk)


class ReturnItemView(LoginRequiredMixin, StaffOnlyMixin, View):
    def get(self, request, pk):
        custody = get_object_or_404(ItemCustody, pk=pk, returned_date__isnull=True)
        return render(request, 'inventory/item_return_form.html', {'custody': custody})

    def post(self, request, pk):
        custody = get_object_or_404(ItemCustody, pk=pk, returned_date__isnull=True)
        custody.returned_date = timezone.now().date()
        custody.return_notes = request.POST.get('return_notes', '').strip()
        custody.received_by = request.user
        custody.save()
        messages.success(request, f'{custody.item.name} has been marked as returned.')
        return redirect('inventory:item_detail', pk=custody.item.pk)


class CustodyListView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    model = ItemCustody
    template_name = 'inventory/custody_list.html'
    context_object_name = 'custody_records'
    paginate_by = 30

    def get_queryset(self):
        qs = ItemCustody.objects.select_related('item', 'issued_by', 'received_by')
        status = self.request.GET.get('status')
        if status == 'active':
            qs = qs.filter(returned_date__isnull=True)
        elif status == 'returned':
            qs = qs.filter(returned_date__isnull=False)
        return qs.order_by('-issued_date')


class BulkQRPrintView(LoginRequiredMixin, StaffOnlyMixin, ListView):
    model = InventoryItem
    template_name = 'inventory/bulk_qr_print.html'
    context_object_name = 'items'

    def get_queryset(self):
        qs = InventoryItem.objects.select_related('category').order_by('name')
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = InventoryCategory.objects.all()
        ctx['selected_category'] = self.request.GET.get('category', '')
        ctx['items_with_urls'] = [
            {'item': item, 'scan_url': self.request.build_absolute_uri(item.get_qr_scan_url())}
            for item in ctx['items']
        ]
        return ctx