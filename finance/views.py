# finance/views.py
import csv
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, Max
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView

from curriculum.models import Term, Session, Standard
from students.models import Student, Parent

from . import services
from .forms import (
    FeeCategoryForm, FeeStructureForm, GenerateInvoicesForm, BankAccountForm,
    InvoiceForm, InvoiceItemFormSet, StaffPaymentForm, ParentPaymentForm,
    PaymentNotificationForm, ExpenseCategoryForm, VendorForm, ExpenseForm,
    ReportFilterForm, FeeTableFilterForm, StudentDiscountForm, StudentFeeExceptionForm,
    InstallmentPlanQuickForm, InstallmentFormSet, StudentPaymentDirectoryFilterForm,
)
from .models import (
    BankAccount, FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment, Receipt,
    StudentAccountLedger, PaymentNotification, ExpenseCategory, Vendor, Expense,
    StudentDiscount, StudentFeeException, InstallmentPlan, Installment,
)
from .permissions import (
    finance_staff_required, finance_admin_required, is_finance_staff, is_parent, is_student_user,
    FinanceStaffRequiredMixin, FinanceAdminRequiredMixin,
)

BASE_TEMPLATE = 'finance/base_finance.html'


def _common_context(**extra):
    ctx = {'base_template': BASE_TEMPLATE}
    ctx.update(extra)
    return ctx


def _base_template_for(user):
    """Staff get the full admin sidebar; parents/students get the minimal 'My Finance' shell."""
    return BASE_TEMPLATE if is_finance_staff(user) else 'finance/base_finance_portal.html'


def _current_term_session():
    term = Term.objects.filter(is_current=True).first()
    session = Session.objects.filter(is_current=True).first()
    return term, session


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    """
    Single entry point for /finance/ — routes to the right dashboard for
    whoever's logged in, rather than showing the school-wide admin view to
    everyone (staff get the full financial overview; parents/students get
    a personal summary of their own account only).
    """
    user = request.user
    if is_finance_staff(user):
        return _staff_dashboard(request)
    if is_parent(user) or is_student_user(user):
        return _student_dashboard(request)
    messages.error(request, "Your account isn't linked to a student or staff finance role yet. "
                             "Please contact the school office.")
    return redirect('pages:portal-home')


def _staff_dashboard(request):
    term, session = _current_term_session()
    summary = services.get_dashboard_summary(term=term, session=session)
    recent_payments = Payment.objects.filter(status=Payment.Status.COMPLETED).select_related(
        'student', 'fee_category', 'receipt').order_by('-date_recorded')[:8]
    top_debtors = services.get_debtors(term=term, session=session)[:8]
    recent_expenses = Expense.objects.select_related('category').order_by('-expense_date')[:8]

    context = _common_context(
        summary=summary, recent_payments=recent_payments, top_debtors=top_debtors,
        recent_expenses=recent_expenses, current_term=term, current_session=session,
        title='Finance Dashboard',
    )
    return render(request, 'finance/dashboard.html', context)


def _student_dashboard(request):
    """A parent/student's own "My Finance" summary — no school-wide data, no admin links."""
    user = request.user
    if is_parent(user):
        children = Student.objects.filter(parent=user.parent).order_by('last_name')
    else:
        children = Student.objects.filter(pk=user.student.pk)

    term, session = _current_term_session()
    child_summaries = []
    for child in children:
        invoices = Invoice.objects.filter(student=child).exclude(status=Invoice.Status.CANCELLED)
        current_invoice = invoices.filter(term=term, session=session).first() if term and session else None
        outstanding = sum((inv.balance for inv in invoices if inv.balance > 0), Decimal('0.00'))
        recent_payments = Payment.objects.filter(
            student=child, status=Payment.Status.COMPLETED
        ).select_related('fee_category', 'receipt').order_by('-payment_date')[:5]
        child_summaries.append({
            'student': child, 'current_invoice': current_invoice, 'outstanding': outstanding,
            'recent_payments': recent_payments,
        })

    context = _common_context(
        child_summaries=child_summaries, current_term=term, current_session=session,
        is_parent_view=is_parent(user), title='My Finance',
        base_template='finance/base_finance_portal.html',
    )
    return render(request, 'finance/student_dashboard.html', context)


# ---------------------------------------------------------------------------
# Fee Categories / Fee Structure / Bank Accounts (setup)
# ---------------------------------------------------------------------------
class FeeCategoryListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = FeeCategory
    template_name = 'finance/fee_category_list.html'
    context_object_name = 'categories'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['base_template'] = BASE_TEMPLATE
        ctx['title'] = 'Fee Categories'
        return ctx


class FeeCategoryCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:fee_category_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Fee Category')
        return ctx


class FeeCategoryUpdateView(LoginRequiredMixin, FinanceStaffRequiredMixin, UpdateView):
    model = FeeCategory
    form_class = FeeCategoryForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:fee_category_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Edit Fee Category')
        return ctx


class FeeStructureListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = FeeStructure
    template_name = 'finance/fee_structure_list.html'
    context_object_name = 'fee_structures'
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset().select_related('student_class', 'fee_category', 'term', 'session')
        term_id = self.request.GET.get('term')
        session_id = self.request.GET.get('session')
        class_id = self.request.GET.get('student_class')
        if term_id:
            qs = qs.filter(term_id=term_id)
        if session_id:
            qs = qs.filter(session_id=session_id)
        if class_id:
            qs = qs.filter(student_class_id=class_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Fee Structure',
                    filter_form=FeeTableFilterForm(self.request.GET or None),
                    terms=Term.objects.all(), sessions=Session.objects.all(), classes=Standard.objects.all())
        return ctx


class FeeStructureCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:fee_structure_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Fee Structure Item')
        return ctx


class FeeStructureUpdateView(LoginRequiredMixin, FinanceStaffRequiredMixin, UpdateView):
    model = FeeStructure
    form_class = FeeStructureForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:fee_structure_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Edit Fee Structure Item')
        return ctx


class FeeStructureDeleteView(LoginRequiredMixin, FinanceStaffRequiredMixin, DeleteView):
    model = FeeStructure
    template_name = 'finance/confirm_delete.html'
    success_url = reverse_lazy('finance:fee_structure_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Delete Fee Structure Item')
        return ctx


# ---------------------------------------------------------------------------
# Student Discounts / Concessions
# ---------------------------------------------------------------------------
class StudentDiscountListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = StudentDiscount
    template_name = 'finance/discount_list.html'
    context_object_name = 'discounts'
    paginate_by = 30

    def get_queryset(self):
        qs = StudentDiscount.objects.select_related('student', 'fee_category', 'term', 'session')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) |
                            Q(reason__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Student Discounts & Concessions')
        return ctx


class StudentDiscountCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = StudentDiscount
    form_class = StudentDiscountForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:discount_list')

    def get_initial(self):
        initial = super().get_initial()
        student_id = self.request.GET.get('student')
        if student_id:
            initial['student'] = get_object_or_404(Student, pk=student_id)
        return initial

    def form_valid(self, form):
        form.instance.approved_by = self.request.user
        response = super().form_valid(form)
        # Refresh any existing invoice for this student/scope so the discount takes effect immediately
        discount = form.instance
        invoices = Invoice.objects.filter(student=discount.student).exclude(status=Invoice.Status.CANCELLED)
        if discount.term_id:
            invoices = invoices.filter(term_id=discount.term_id)
        if discount.session_id:
            invoices = invoices.filter(session_id=discount.session_id)
        for invoice in invoices:
            services.generate_invoice_for_student(discount.student, invoice.term, invoice.session,
                                                    user=self.request.user)
        messages.success(self.request, f"Discount granted. {invoices.count()} existing invoice(s) refreshed.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Grant Student Discount')
        return ctx


class StudentDiscountUpdateView(LoginRequiredMixin, FinanceStaffRequiredMixin, UpdateView):
    model = StudentDiscount
    form_class = StudentDiscountForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:discount_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        discount = form.instance
        invoices = Invoice.objects.filter(student=discount.student).exclude(status=Invoice.Status.CANCELLED)
        for invoice in invoices:
            services.generate_invoice_for_student(discount.student, invoice.term, invoice.session,
                                                    user=self.request.user)
        messages.success(self.request, "Discount updated and affected invoices refreshed.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Edit Student Discount')
        return ctx


@login_required
@finance_staff_required
def deactivate_discount(request, pk):
    discount = get_object_or_404(StudentDiscount, pk=pk)
    discount.is_active = False
    discount.save(update_fields=['is_active'])
    invoices = Invoice.objects.filter(student=discount.student).exclude(status=Invoice.Status.CANCELLED)
    for invoice in invoices:
        services.generate_invoice_for_student(discount.student, invoice.term, invoice.session, user=request.user)
    messages.success(request, "Discount deactivated and affected invoices refreshed.")
    return redirect('finance:discount_list')


# ---------------------------------------------------------------------------
# Student Fee Exceptions (per-student exclude/include overrides)
# ---------------------------------------------------------------------------
def _refresh_invoice_for_exception(exception, user):
    """After an exception is added/removed, refresh that student's invoice for the affected term/session."""
    invoice = Invoice.objects.filter(
        student=exception.student, term=exception.fee_structure.term, session=exception.fee_structure.session,
    ).exclude(status=Invoice.Status.CANCELLED).first()
    if invoice:
        services.generate_invoice_for_student(exception.student, invoice.term, invoice.session, user=user)
        return True
    return False


class StudentFeeExceptionListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = StudentFeeException
    template_name = 'finance/fee_exception_list.html'
    context_object_name = 'exceptions'
    paginate_by = 30

    def get_queryset(self):
        qs = StudentFeeException.objects.select_related(
            'student', 'fee_structure__fee_category', 'fee_structure__term', 'fee_structure__session',
        )
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) |
                            Q(reason__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Student Fee Exceptions')
        return ctx


class StudentFeeExceptionCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = StudentFeeException
    form_class = StudentFeeExceptionForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:fee_exception_list')

    def get_initial(self):
        initial = super().get_initial()
        student_id = self.request.GET.get('student')
        if student_id:
            initial['student'] = get_object_or_404(Student, pk=student_id)
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        refreshed = _refresh_invoice_for_exception(form.instance, self.request.user)
        if refreshed:
            messages.success(self.request, "Fee exception saved and the student's invoice was refreshed.")
        else:
            messages.success(self.request, "Fee exception saved. It will apply next time this student's "
                                            "invoice is generated for that term/session.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Fee Exception',
                    help_text="Exclude a normally-mandatory fee for one student (e.g. a returning student "
                              "skipping the registration fee), or include an optional fee just for one "
                              "student (e.g. a mid-term uniform request).")
        return ctx


@login_required
@finance_staff_required
def delete_fee_exception(request, pk):
    exception = get_object_or_404(StudentFeeException, pk=pk)
    student, fee_structure = exception.student, exception.fee_structure
    exception.delete()
    invoice = Invoice.objects.filter(
        student=student, term=fee_structure.term, session=fee_structure.session,
    ).exclude(status=Invoice.Status.CANCELLED).first()
    if invoice:
        services.generate_invoice_for_student(student, invoice.term, invoice.session, user=request.user)
    messages.success(request, "Fee exception removed and the student's invoice was refreshed.")
    return redirect('finance:fee_exception_list')


class BankAccountListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = BankAccount
    template_name = 'finance/bank_account_list.html'
    context_object_name = 'accounts'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='School Bank Accounts')
        return ctx


class BankAccountCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = BankAccount
    form_class = BankAccountForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:bank_account_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Bank Account')
        return ctx


class BankAccountUpdateView(LoginRequiredMixin, FinanceStaffRequiredMixin, UpdateView):
    model = BankAccount
    form_class = BankAccountForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:bank_account_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Edit Bank Account')
        return ctx


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------
class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'finance/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('student', 'term', 'session').prefetch_related(
            'payments__receipt').order_by('-issue_date')
        student_id = self.request.GET.get('student')
        if not is_finance_staff(user):
            if is_parent(user):
                qs = qs.filter(student__parent=user.parent)
                if student_id:
                    # Safe to narrow further — still constrained to their own children above.
                    qs = qs.filter(student_id=student_id)
            elif is_student_user(user):
                qs = qs.filter(student=user.student)
            else:
                qs = qs.none()
        else:
            if student_id:
                qs = qs.filter(student_id=student_id)

        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        if q:
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) |
                            Q(invoice_number__icontains=q))
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=_base_template_for(self.request.user), title='Invoices',
                    status_choices=Invoice.Status.choices, is_finance_staff=is_finance_staff(self.request.user))
        return ctx


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related('student', 'term', 'session'), pk=pk)
    user = request.user
    if not is_finance_staff(user):
        allowed = (is_parent(user) and invoice.student.parent_id == getattr(user.parent, 'id', None)) or \
                  (is_student_user(user) and invoice.student_id == user.student.id)
        if not allowed:
            return HttpResponseForbidden("You do not have permission to view this invoice.")

    plan = getattr(invoice, 'installment_plan', None)
    context = {
        'invoice': invoice,
        'items': invoice.items.select_related('fee_category'),
        'bank_accounts': BankAccount.objects.filter(is_active=True),
        'school': _get_school_identity(),
        'today': timezone.localdate(),
        'installment_plan': plan,
        'installment_breakdown': services.get_installment_breakdown(plan) if plan else None,
    }
    return render(request, 'finance/invoice_detail.html', context)


@login_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    plan = getattr(invoice, 'installment_plan', None)
    context = {
        'invoice': invoice,
        'items': invoice.items.select_related('fee_category'),
        'bank_accounts': BankAccount.objects.filter(is_active=True),
        'school': _get_school_identity(),
        'today': timezone.localdate(),
        'installment_plan': plan,
        'installment_breakdown': services.get_installment_breakdown(plan) if plan else None,
        'is_pdf': True,
    }
    response = services.render_to_pdf('finance/invoice_detail.html', context,
                                       filename=f"{invoice.invoice_number}.pdf")
    if not response:
        messages.error(request, "Could not generate the invoice PDF. Please try again.")
        return redirect('finance:invoice_detail', pk=pk)
    return response


@login_required
@finance_staff_required
def invoice_create(request):
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            invoice.save()
            formset = InvoiceItemFormSet(request.POST, instance=invoice)
            if formset.is_valid():
                formset.save()
                services.sync_invoice_status(invoice)
                messages.success(request, f"Invoice {invoice.invoice_number} created.")
                return redirect('finance:invoice_detail', pk=invoice.pk)
        else:
            formset = InvoiceItemFormSet(request.POST)
    else:
        form = InvoiceForm()
        formset = InvoiceItemFormSet()

    context = _common_context(form=form, formset=formset, title='Create Invoice')
    return render(request, 'finance/invoice_form.html', context)


@login_required
@finance_staff_required
def invoice_edit_items(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        formset = InvoiceItemFormSet(request.POST, instance=invoice)
        if formset.is_valid():
            formset.save()
            services.sync_invoice_status(invoice)
            messages.success(request, "Invoice items updated.")
            return redirect('finance:invoice_detail', pk=invoice.pk)
    else:
        formset = InvoiceItemFormSet(instance=invoice)
    context = _common_context(invoice=invoice, formset=formset, title=f'Edit Items — {invoice.invoice_number}')
    return render(request, 'finance/invoice_items_form.html', context)


@login_required
@finance_staff_required
def manage_installment_plan(request, invoice_pk):
    """
    Set up or fine-tune an invoice's installment schedule. Parents still
    pay however they normally would (staff-recorded, self-service, or a
    verified bank transfer) — this just defines due tranches that the
    breakdown table on the invoice checks their cumulative payments against.
    """
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    plan = getattr(invoice, 'installment_plan', None)
    quick_form = InstallmentPlanQuickForm()
    formset = InstallmentFormSet(instance=plan) if plan else None

    if request.method == 'POST' and request.POST.get('action') == 'quick_generate':
        quick_form = InstallmentPlanQuickForm(request.POST)
        if quick_form.is_valid():
            count = quick_form.cleaned_data['count']
            first_due = quick_form.cleaned_data.get('first_due_date')
            interval = quick_form.cleaned_data.get('interval_days') or 30
            due_dates = [first_due + timedelta(days=interval * i) for i in range(count)] if first_due else None
            installments_data = services.build_equal_installments(invoice, count, due_dates=due_dates)
            services.create_installment_plan(invoice, installments_data, user=request.user)
            messages.success(request, f"{count}-installment plan created — you can fine-tune amounts, "
                                       f"labels, or due dates below.")
            return redirect('finance:manage_installment_plan', invoice_pk=invoice.pk)

    elif request.method == 'POST' and request.POST.get('action') == 'save_schedule' and plan:
        formset = InstallmentFormSet(request.POST, instance=plan)
        if formset.is_valid():
            total = sum(
                (f.cleaned_data.get('amount_due') or Decimal('0.00'))
                for f in formset.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')
            )
            if total != invoice.total_amount:
                messages.error(request, f"Installments must add up to the invoice total "
                                         f"({invoice.total_amount}); they currently add up to {total}.")
            else:
                instances = formset.save(commit=False)
                for obj in formset.deleted_objects:
                    obj.delete()
                next_seq = (plan.installments.aggregate(Max('sequence'))['sequence__max'] or 0) + 1
                for obj in instances:
                    if obj.pk is None:
                        obj.sequence = next_seq
                        next_seq += 1
                    obj.plan = plan
                    obj.save()
                messages.success(request, "Installment schedule updated.")
                return redirect('finance:manage_installment_plan', invoice_pk=invoice.pk)

    breakdown = services.get_installment_breakdown(plan) if plan else None
    context = _common_context(
        invoice=invoice, plan=plan, quick_form=quick_form, formset=formset, breakdown=breakdown,
        title=f'Installment Plan — {invoice.invoice_number}',
    )
    return render(request, 'finance/installment_plan_form.html', context)


@login_required
@finance_staff_required
def delete_installment_plan(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    plan = getattr(invoice, 'installment_plan', None)
    if plan:
        plan.delete()
        messages.success(request, "Installment plan removed. The invoice reverts to a single lump-sum balance.")
    return redirect('finance:invoice_detail', pk=invoice.pk)


@login_required
@finance_staff_required
@permission_required('finance.generate_invoices', raise_exception=True)
def generate_invoices(request):
    if request.method == 'POST':
        form = GenerateInvoicesForm(request.POST)
        if form.is_valid():
            invoices = services.bulk_generate_invoices(
                student_class=form.cleaned_data['student_class'],
                term=form.cleaned_data['term'],
                session=form.cleaned_data['session'],
                user=request.user,
            )
            messages.success(request, f"Generated/updated {len(invoices)} invoice(s) for "
                                       f"{form.cleaned_data['student_class']}.")
            return redirect('finance:invoice_list')
    else:
        form = GenerateInvoicesForm()
    context = _common_context(form=form, title='Bulk Generate Invoices')
    return render(request, 'finance/generate_invoices.html', context)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
@login_required
def student_search_ajax(request):
    query = request.GET.get('q', '')
    students = Student.objects.all()
    if query:
        students = students.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
    students = students.values('id', 'first_name', 'last_name')[:20]
    results = [{'id': s['id'], 'text': f"{s['first_name']} {s['last_name']}"} for s in students]
    return JsonResponse({'results': results})


@login_required
def student_invoices_ajax(request, student_id):
    """Returns a student's open invoices — used by the payment form's dynamic dropdown."""
    invoices = Invoice.objects.filter(student_id=student_id).exclude(status=Invoice.Status.CANCELLED)
    results = [{
        'id': inv.id,
        'text': f"{inv.invoice_number} — {inv.term} {inv.session} (Balance: {inv.balance})",
        'balance': str(inv.balance),
    } for inv in invoices if inv.balance > 0]
    return JsonResponse({'results': results})


@login_required
@finance_staff_required
def make_payment(request):
    if request.method == 'POST':
        form = StaffPaymentForm(request.POST)
        if form.is_valid():
            payment = services.record_payment(
                user=request.user,
                student=form.cleaned_data['student'],
                invoice=form.cleaned_data.get('invoice'),
                fee_category=form.cleaned_data.get('fee_category'),
                amount_received=form.cleaned_data['amount_received'],
                payment_method=form.cleaned_data['payment_method'],
                payment_date=form.cleaned_data['payment_date'],
                transaction_id=form.cleaned_data.get('transaction_id'),
                notes=form.cleaned_data.get('notes', ''),
            )
            if hasattr(payment, 'receipt'):
                messages.success(request, f"Payment recorded. Receipt #{payment.receipt.receipt_number}.")
                return redirect('finance:receipt_detail', pk=payment.receipt.pk)
            messages.success(request, "Payment recorded.")
            return redirect('finance:payment_list')
    else:
        initial = {}
        preselected_id = request.GET.get('student')
        if preselected_id:
            initial['student'] = get_object_or_404(Student, pk=preselected_id)
        form = StaffPaymentForm(initial=initial)
    context = _common_context(form=form, title='Record a Payment')
    return render(request, 'finance/payment_form.html', context)


@login_required
@finance_staff_required
def student_payment_directory(request):
    """
    Class-filterable, searchable list of students for staff to pick from when
    recording a payment — replaces the old "scroll through every student in
    a giant dropdown" flow. Each row links straight into the payment form
    with that student already selected.
    """
    filter_form = StudentPaymentDirectoryFilterForm(request.GET or None)
    students = Student.objects.select_related('current_class').order_by('last_name', 'first_name')

    student_class = q = None
    if filter_form.is_valid():
        student_class = filter_form.cleaned_data.get('student_class')
        q = filter_form.cleaned_data.get('q')
        if student_class:
            students = students.filter(current_class=student_class)
        if q:
            students = students.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(USN__icontains=q)
            )

    term, session = _current_term_session()
    paginator = Paginator(students, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Current-term balance for just the students on this page (cheap — 30 rows, not the whole school).
    ledgers = {}
    if term and session:
        student_ids = [s.pk for s in page_obj]
        ledgers = {
            ledger.student_id: ledger
            for ledger in StudentAccountLedger.objects.filter(
                student_id__in=student_ids, term=term, session=session)
        }

    rows = [{'student': s, 'ledger': ledgers.get(s.pk)} for s in page_obj]

    context = _common_context(
        filter_form=filter_form, rows=rows, page_obj=page_obj, is_paginated=page_obj.has_other_pages(),
        classes=Standard.objects.all().order_by('name'), current_term=term, current_session=session,
        title='Record a Payment',
    )
    return render(request, 'finance/payment_directory.html', context)


@login_required
def make_parent_payment(request):
    if not is_parent(request.user):
        messages.error(request, "You do not have permission to access this page.")
        return redirect('pages:portal-home')

    parent = request.user.parent
    if request.method == 'POST':
        form = ParentPaymentForm(request.POST, parent=parent)
        if form.is_valid():
            payment = services.record_payment(
                user=request.user,
                student=form.cleaned_data['student'],
                invoice=form.cleaned_data['invoice'],
                amount_received=form.cleaned_data['amount_received'],
                payment_method=form.cleaned_data['payment_method'],
                payment_date=form.cleaned_data['payment_date'],
                transaction_id=form.cleaned_data.get('transaction_id'),
                notes=form.cleaned_data.get('notes', ''),
            )
            if hasattr(payment, 'receipt'):
                messages.success(request, f"Payment recorded. Receipt #{payment.receipt.receipt_number}.")
                return redirect('finance:receipt_detail', pk=payment.receipt.pk)
            messages.success(request, "Payment recorded.")
            return redirect('finance:payment_list')
    else:
        initial = {}
        preselected_student_id = request.GET.get('student')
        if preselected_student_id:
            initial['student'] = get_object_or_404(Student, pk=preselected_student_id, parent=parent)
        preselected_invoice_id = request.GET.get('invoice')
        if preselected_invoice_id:
            initial['invoice'] = get_object_or_404(Invoice, pk=preselected_invoice_id, student__parent=parent)
        form = ParentPaymentForm(parent=parent, initial=initial)
    context = _common_context(form=form, title='Make a Payment', base_template='finance/base_finance_portal.html')
    return render(request, 'finance/parent_payment_form.html', context)


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'finance/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.filter(status=Payment.Status.COMPLETED).select_related(
            'student', 'fee_category', 'term', 'session', 'invoice', 'receipt')

        if not is_finance_staff(user):
            if is_parent(user):
                qs = qs.filter(student__parent=user.parent)
            elif is_student_user(user):
                qs = qs.filter(student=user.student)
            else:
                qs = qs.none()

        term_id = self.request.GET.get('term')
        session_id = self.request.GET.get('session')
        category_id = self.request.GET.get('fee_category')
        q = self.request.GET.get('q')
        if term_id:
            qs = qs.filter(term_id=term_id)
        if session_id:
            qs = qs.filter(session_id=session_id)
        if category_id:
            qs = qs.filter(fee_category_id=category_id)
        if q and is_finance_staff(user):
            qs = qs.filter(Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) |
                            Q(transaction_id__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=_base_template_for(self.request.user), title='Payment History',
                    terms=Term.objects.all(), sessions=Session.objects.all(),
                    categories=FeeCategory.objects.all(), is_finance_staff=is_finance_staff(self.request.user))
        return ctx


@login_required
def receipt_detail(request, pk):
    receipt = get_object_or_404(Receipt.objects.select_related('payment__student', 'payment__invoice'), pk=pk)
    payment = receipt.payment
    user = request.user
    if not is_finance_staff(user):
        allowed = (is_parent(user) and payment.student.parent_id == getattr(user.parent, 'id', None)) or \
                  (is_student_user(user) and payment.student_id == user.student.id)
        if not allowed:
            return HttpResponseForbidden("You do not have permission to view this receipt.")

    context = {
        'receipt': receipt, 'payment': payment, 'invoice': payment.invoice,
        'school': _get_school_identity(),
    }
    return render(request, 'finance/receipt_detail.html', context)


@login_required
def receipt_pdf(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk)
    context = {'receipt': receipt, 'payment': receipt.payment, 'invoice': receipt.payment.invoice,
               'school': _get_school_identity()}
    response = services.render_to_pdf('finance/receipt_detail.html', context,
                                       filename=f"{receipt.receipt_number}.pdf")
    if not response:
        messages.error(request, "Could not generate the receipt PDF. Please try again.")
        return redirect('finance:receipt_detail', pk=pk)
    return response


# ---------------------------------------------------------------------------
# Payment Notifications (offline payment proof)
# ---------------------------------------------------------------------------
@login_required
def notify_payment(request):
    user = request.user
    parent_obj = getattr(user, 'parent', None) if is_parent(user) else None
    student_for_display = user.student if is_student_user(user) else (
        Student.objects.filter(parent=parent_obj).first() if parent_obj else None)

    if request.method == 'POST':
        form = PaymentNotificationForm(request.POST, request.FILES, user=user, parent=parent_obj)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.notified_by = user
            if not user.is_staff and student_for_display and not is_parent(user):
                notification.student = student_for_display
            notification.save()
            messages.success(request, "Payment notification submitted. It is now pending review.")
            return redirect('finance:payment_notification_success')
    else:
        form = PaymentNotificationForm(user=user, parent=parent_obj)

    context = _common_context(form=form, student_for_display=student_for_display, title='Submit Proof of Payment',
                               base_template=_base_template_for(user))
    return render(request, 'finance/notify_payment.html', context)


@login_required
def payment_notification_success(request):
    context = _common_context(title='Submitted', base_template=_base_template_for(request.user))
    return render(request, 'finance/notification_success.html', context)


class PaymentNotificationListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = PaymentNotification
    template_name = 'finance/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        return PaymentNotification.objects.filter(status='PENDING').select_related('student', 'bank_account')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Pending Payment Notifications')
        return ctx


class UserPaymentNotificationListView(LoginRequiredMixin, ListView):
    model = PaymentNotification
    template_name = 'finance/my_notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        q_filter = Q(notified_by=user)
        if is_student_user(user):
            q_filter |= Q(student=user.student)
        if is_parent(user):
            q_filter |= Q(student__parent=user.parent)
        return PaymentNotification.objects.filter(q_filter).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=_base_template_for(self.request.user), title='My Payment Submissions')
        return ctx


@login_required
@finance_staff_required
def process_notification(request, pk):
    """Verify a PaymentNotification: turn it into a real, receipted Payment."""
    notification = get_object_or_404(PaymentNotification, pk=pk)
    action = request.POST.get('action') if request.method == 'POST' else None

    if request.method == 'POST' and action == 'approve':
        invoice_id = request.POST.get('invoice')
        invoice = Invoice.objects.filter(pk=invoice_id, student=notification.student).first() if invoice_id else None
        payment = services.record_payment(
            user=request.user, student=notification.student, invoice=invoice,
            amount_received=notification.amount_paid, payment_method='bank_transfer',
            payment_date=notification.payment_date, transaction_id=notification.transaction_id,
            notes=f"Verified from payment notification #{notification.pk}.",
        )
        notification.status = PaymentNotification.Status.PROCESSED
        notification.processed_by = request.user
        notification.processed_at = timezone.now()
        notification.resulting_payment = payment
        notification.save()
        messages.success(request, "Notification approved and payment recorded.")
        return redirect('finance:notification_list')

    elif request.method == 'POST' and action == 'reject':
        notification.status = PaymentNotification.Status.REJECTED
        notification.processed_by = request.user
        notification.processed_at = timezone.now()
        notification.save()
        messages.info(request, "Notification rejected.")
        return redirect('finance:notification_list')

    invoices = Invoice.objects.filter(student=notification.student).exclude(status=Invoice.Status.CANCELLED)
    context = _common_context(notification=notification, invoices=invoices, title='Review Notification')
    return render(request, 'finance/process_notification.html', context)


# ---------------------------------------------------------------------------
# Fee Table (printable / exportable)
# ---------------------------------------------------------------------------
@login_required
def fee_table(request):
    staff_view = is_finance_staff(request.user)
    form = FeeTableFilterForm(request.GET or None) if staff_view else None
    qs = FeeStructure.objects.select_related('student_class', 'fee_category', 'term', 'session')

    if staff_view:
        term = session = student_class = None
        if form.is_valid():
            term = form.cleaned_data.get('term')
            session = form.cleaned_data.get('session')
            student_class = form.cleaned_data.get('student_class')
    else:
        # Parents/students always see the current term's published schedule only —
        # no browsing other terms/sessions, and no filter form to do it with.
        term, session = _current_term_session()
        student_class = None

    if term:
        qs = qs.filter(term=term)
    if session:
        qs = qs.filter(session=session)
    if student_class:
        qs = qs.filter(Q(student_class=student_class) | Q(student_class__isnull=True))

    qs = qs.order_by('student_class__name', 'fee_category__name')

    # Group rows by class for a clean printable table
    grouped = {}
    for row in qs:
        key = row.student_class.name if row.student_class else 'All Classes'
        grouped.setdefault(key, []).append(row)

    class_totals = {k: sum((r.amount for r in v), Decimal('0.00')) for k, v in grouped.items()}

    context = {
        'form': form, 'grouped': grouped, 'class_totals': class_totals,
        'term': term, 'session': session, 'student_class': student_class,
        'school': _get_school_identity(), 'today': timezone.localdate(),
        'base_template': BASE_TEMPLATE if staff_view else 'finance/base_finance_portal.html',
        'staff_view': staff_view,
    }
    return render(request, 'finance/fee_table.html', context)


@login_required
def fee_table_pdf(request):
    staff_view = is_finance_staff(request.user)
    form = FeeTableFilterForm(request.GET or None) if staff_view else None
    qs = FeeStructure.objects.select_related('student_class', 'fee_category', 'term', 'session')

    if staff_view:
        term = session = student_class = None
        if form.is_valid():
            term = form.cleaned_data.get('term')
            session = form.cleaned_data.get('session')
            student_class = form.cleaned_data.get('student_class')
    else:
        term, session = _current_term_session()
        student_class = None

    if term:
        qs = qs.filter(term=term)
    if session:
        qs = qs.filter(session=session)
    if student_class:
        qs = qs.filter(Q(student_class=student_class) | Q(student_class__isnull=True))
    qs = qs.order_by('student_class__name', 'fee_category__name')

    grouped = {}
    for row in qs:
        key = row.student_class.name if row.student_class else 'All Classes'
        grouped.setdefault(key, []).append(row)
    class_totals = {k: sum((r.amount for r in v), Decimal('0.00')) for k, v in grouped.items()}

    context = {
        'form': form, 'grouped': grouped, 'class_totals': class_totals,
        'term': term, 'session': session, 'student_class': student_class,
        'school': _get_school_identity(), 'today': timezone.localdate(), 'is_pdf': True,
        'staff_view': staff_view,
    }
    response = services.render_to_pdf('finance/fee_table.html', context, filename='fee_table.pdf')
    if not response:
        messages.error(request, "Could not generate the fee table PDF.")
        return redirect('finance:fee_table')
    return response


# ---------------------------------------------------------------------------
# Debtors report
# ---------------------------------------------------------------------------
@login_required
@finance_staff_required
def resync_ledgers(request):
    """
    Self-service "fix stale balances" button for staff — recomputes every
    student's cached ledger from their actual invoices/payments, without
    needing shell/admin access. Same underlying logic as the
    `sync_finance_ledgers` management command and the admin's
    "Recalculate" action.
    """
    invoices = Invoice.objects.select_related('student', 'term', 'session')
    seen = set()
    for invoice in invoices:
        services.sync_invoice_status(invoice)
        key = (invoice.student_id, invoice.term_id, invoice.session_id)
        if key not in seen:
            services.sync_student_ledger(invoice.student, invoice.term, invoice.session)
            seen.add(key)
    messages.success(request, f"Recalculated {len(seen)} student ledger(s) from their invoices and payments.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('finance:debtors_report'))


@login_required
@finance_staff_required
def debtors_report(request):
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    class_id = request.GET.get('student_class')

    term = Term.objects.filter(pk=term_id).first() if term_id else None
    session = Session.objects.filter(pk=session_id).first() if session_id else None
    student_class = Standard.objects.filter(pk=class_id).first() if class_id else None

    if not term or not session:
        cur_term, cur_session = _current_term_session()
        term = term or cur_term
        session = session or cur_session

    debtors = services.get_debtors(term=term, session=session, student_class=student_class)
    total_outstanding = debtors.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    if request.GET.get('format') == 'csv':
        return _debtors_csv(debtors, term, session)
    if request.GET.get('format') == 'pdf':
        context = {'debtors': debtors, 'term': term, 'session': session, 'total_outstanding': total_outstanding,
                   'school': _get_school_identity(), 'today': timezone.localdate()}
        response = services.render_to_pdf('finance/debtors_report.html', context, filename='debtors_report.pdf')
        return response or redirect('finance:debtors_report')

    context = _common_context(
        debtors=debtors, term=term, session=session, total_outstanding=total_outstanding,
        terms=Term.objects.all(), sessions=Session.objects.all(), classes=Standard.objects.all(),
        selected_class=student_class, title='Debtors Report',
    )
    return render(request, 'finance/debtors_report.html', context)


def _debtors_csv(debtors, term, session):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="debtors_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Student', 'Class', 'Term', 'Session', 'Total Invoiced', 'Total Paid', 'Balance'])
    for entry in debtors:
        writer.writerow([
            entry.student.get_full_name(),
            getattr(entry.student.current_class, 'name', ''),
            entry.term.name, entry.session.name,
            entry.total_invoiced, entry.total_paid, entry.balance,
        ])
    return response


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
class ExpenseListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = Expense
    template_name = 'finance/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 25

    def get_queryset(self):
        qs = Expense.objects.select_related('category', 'vendor').order_by('-expense_date')
        category_id = self.request.GET.get('category')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(vendor__name__icontains=q) | Q(reference_number__icontains=q))
        return qs

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get('format')
        if export_format in ('csv', 'pdf'):
            queryset = self.get_queryset()
            if export_format == 'csv':
                return self._export_csv(queryset)
            return self._export_pdf(request, queryset)
        return super().get(request, *args, **kwargs)

    def _export_csv(self, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
        writer = csv.writer(response)
        writer.writerow(['Title', 'Category', 'Vendor', 'Amount', 'Date', 'Term', 'Session',
                          'Payment Method', 'Reference', 'Status', 'Recorded By'])
        for e in queryset:
            writer.writerow([
                e.title, e.category.name, e.vendor.name if e.vendor else '',
                e.amount, e.expense_date, e.term or '', e.session or '',
                e.get_payment_method_display(), e.reference_number, e.get_status_display(),
                e.recorded_by.get_username() if e.recorded_by else '',
            ])
        return response

    def _export_pdf(self, request, queryset):
        total = queryset.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        context = {
            'expenses': queryset, 'total_amount': total,
            'category': ExpenseCategory.objects.filter(pk=request.GET.get('category')).first(),
            'status': dict(Expense.Status.choices).get(request.GET.get('status')),
            'q': request.GET.get('q'),
            'school': _get_school_identity(), 'today': timezone.localdate(),
        }
        response = services.render_to_pdf('finance/expense_report.html', context, filename='expenses.pdf')
        if not response:
            messages.error(request, "Could not generate the expense report PDF.")
            return redirect('finance:expense_list')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        total = self.get_queryset().aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        ctx.update(base_template=BASE_TEMPLATE, title='Expenses', categories=ExpenseCategory.objects.all(),
                   status_choices=Expense.Status.choices, total_amount=total)
        return ctx


class ExpenseCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:expense_list')

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, "Expense recorded.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Record Expense')
        return ctx


class ExpenseUpdateView(LoginRequiredMixin, FinanceStaffRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:expense_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Edit Expense')
        return ctx


class ExpenseDeleteView(LoginRequiredMixin, FinanceStaffRequiredMixin, DeleteView):
    model = Expense
    template_name = 'finance/confirm_delete.html'
    success_url = reverse_lazy('finance:expense_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Delete Expense')
        return ctx


@login_required
@permission_required('finance.approve_expense', raise_exception=True)
def approve_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    expense.status = Expense.Status.APPROVED
    expense.approved_by = request.user
    expense.save(update_fields=['status', 'approved_by'])
    messages.success(request, f"Expense '{expense.title}' approved.")
    return redirect('finance:expense_list')


class ExpenseCategoryListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'finance/expense_category_list.html'
    context_object_name = 'categories'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Expense Categories')
        return ctx


class ExpenseCategoryCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:expense_category_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Expense Category')
        return ctx


class VendorListView(LoginRequiredMixin, FinanceStaffRequiredMixin, ListView):
    model = Vendor
    template_name = 'finance/vendor_list.html'
    context_object_name = 'vendors'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Vendors / Payees')
        return ctx


class VendorCreateView(LoginRequiredMixin, FinanceStaffRequiredMixin, CreateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'finance/simple_form.html'
    success_url = reverse_lazy('finance:vendor_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(base_template=BASE_TEMPLATE, title='Add Vendor')
        return ctx


# ---------------------------------------------------------------------------
# Profit & Loss / Reports
# ---------------------------------------------------------------------------
@login_required
@finance_admin_required
def profit_loss_report(request):
    form = ReportFilterForm(request.GET or None)
    start_date = end_date = term = session = None
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        term = form.cleaned_data.get('term')
        session = form.cleaned_data.get('session')

    report = services.get_profit_and_loss(start_date=start_date, end_date=end_date, term=term, session=session)

    if request.GET.get('format') == 'pdf':
        context = dict(report, school=_get_school_identity(), today=timezone.localdate())
        response = services.render_to_pdf('finance/profit_loss_report.html', context, filename='profit_and_loss.pdf')
        return response or redirect('finance:profit_loss_report')

    context = _common_context(form=form, title='Profit & Loss Statement', **report)
    return render(request, 'finance/profit_loss_report.html', context)


@login_required
@finance_staff_required
def total_payments_report(request):
    form = ReportFilterForm(request.GET or None)
    qs = Payment.objects.filter(status=Payment.Status.COMPLETED).select_related('student', 'fee_category')
    if form.is_valid():
        if form.cleaned_data.get('start_date'):
            qs = qs.filter(payment_date__gte=form.cleaned_data['start_date'])
        if form.cleaned_data.get('end_date'):
            qs = qs.filter(payment_date__lte=form.cleaned_data['end_date'])
        if form.cleaned_data.get('term'):
            qs = qs.filter(term=form.cleaned_data['term'])
        if form.cleaned_data.get('session'):
            qs = qs.filter(session=form.cleaned_data['session'])

    total = qs.aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
    breakdown = qs.values('fee_category__name').annotate(total=Sum('amount_received')).order_by('-total')

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="total_payments_report.csv"'
        writer = csv.writer(response)
        writer.writerow(['Student', 'Category', 'Term', 'Session', 'Amount', 'Method', 'Date'])
        for p in qs.order_by('-payment_date'):
            writer.writerow([p.student.get_full_name(), p.fee_category.name, p.term.name, p.session.name,
                              p.amount_received, p.get_payment_method_display(), p.payment_date])
        return response

    context = _common_context(form=form, payments=qs.order_by('-payment_date')[:500], total=total,
                               breakdown=breakdown, title='Total Payments Report')
    return render(request, 'finance/total_payments_report.html', context)


def _get_school_identity():
    try:
        from curriculum.models import SchoolIdentity
        return SchoolIdentity.objects.first()
    except Exception:
        return None
