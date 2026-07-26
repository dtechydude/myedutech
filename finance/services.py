# finance/services.py
"""
Business-logic layer for the Finance app.

Keeping this logic out of models/views means:
    - The same functions power the web UI, the REST API, the Django admin,
      and management commands (e.g. a nightly "mark overdue invoices" job)
      without duplication.
    - Everything that mutates money-related state runs inside a single
      ``transaction.atomic()`` block, so a failure midway never leaves
      half-updated invoices/ledgers behind.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
import os

from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Q, F, DecimalField
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.template.loader import get_template
from django.utils import timezone

from .models import (
    Invoice, InvoiceItem, Payment, Receipt, FeeStructure, FeeCategory, StudentDiscount,
    StudentAccountLedger, StudentLedgerEntry, Expense, ExpenseCategory, StudentFeeException,
    InstallmentPlan, Installment,
)

ZERO = Decimal('0.00')


def get_current_term_session():
    """The school's currently-marked Term/Session, or (None, None) if neither is set yet."""
    from curriculum.models import Term, Session
    term = Term.objects.filter(is_current=True).first()
    session = Session.objects.filter(is_current=True).first()
    return term, session


def get_best_discount(student, fee_category, term, session, original_amount):
    """
    Finds every active StudentDiscount that matches this student/line scope
    and returns the single one giving the LARGEST reduction (discounts
    don't stack — see StudentDiscount's docstring for why), along with the
    Naira amount it knocks off. Returns (None, ZERO) if nothing applies.
    """
    candidates = StudentDiscount.objects.filter(student=student, is_active=True).filter(
        Q(fee_category=fee_category) | Q(fee_category__isnull=True)
    ).filter(
        Q(term=term) | Q(term__isnull=True)
    ).filter(
        Q(session=session) | Q(session__isnull=True)
    )

    best_rule, best_reduction = None, ZERO
    for rule in candidates:
        if not rule.matches(fee_category, term, session):
            continue
        reduction = rule.reduction_for(original_amount)
        if reduction > best_reduction:
            best_rule, best_reduction = rule, reduction
    return best_rule, best_reduction


# ---------------------------------------------------------------------------
# Document numbering
# ---------------------------------------------------------------------------
# invoice_number/receipt_number are assigned directly inside Invoice.save()
# and Receipt.save() (see models.py) rather than here — that keeps
# numbering from depending on finance/signals.py being imported correctly,
# which is what caused invoices to occasionally be created with a blank
# number. If you need the exact format elsewhere, it's:
#   INV-{issue_date:%Y%m}-{pk:06d}   and   RCT-{issue_date:%Y%m}-{pk:06d}


# ---------------------------------------------------------------------------
# Invoicing
# ---------------------------------------------------------------------------
@transaction.atomic
def generate_invoice_for_student(student, term, session, user=None, extra_items=None):
    """
    Creates (or refreshes) a student's invoice for a term/session from the
    matching FeeStructure rows (class-specific rows take priority over
    "all classes" rows with the same fee category).

    Per-student adjustments are applied automatically:
        - StudentFeeException can EXCLUDE a normally-mandatory fee for one
          student (e.g. a returning student skips the new-intake
          registration fee that the rest of the class pays), or INCLUDE an
          otherwise-optional fee just for one student (e.g. one student
          requests an extra uniform set — nobody else's invoice changes).
        - StudentDiscount reduces the amount of any fee that DOES apply to
          the student (sibling discount, staff-ward waiver, scholarship).
        - FeeStructure.is_mandatory=False rows are skipped by default and
          only billed to students with a matching INCLUDE exception.

    ``extra_items`` — optional list of dicts like
        {'fee_category': <FeeCategory>, 'description': 'Late registration', 'amount': Decimal('2000')}
    for one-off charges that aren't part of the standard fee structure at all.

    Returns the Invoice instance.
    """
    invoice, _created = Invoice.objects.get_or_create(
        student=student, term=term, session=session,
        defaults={'created_by': user, 'status': Invoice.Status.ISSUED},
    )

    student_class = getattr(student, 'current_class', None)

    structures = FeeStructure.objects.filter(term=term, session=session).filter(
        Q(student_class=student_class) | Q(student_class__isnull=True)
    ).select_related('fee_category', 'student_class')

    # Prefer the class-specific fee over a same-category "all classes" fee.
    by_category = {}
    for structure in structures:
        key = (structure.fee_category_id, structure.label)
        existing = by_category.get(key)
        if existing is None or (existing.student_class_id is None and structure.student_class_id is not None):
            by_category[key] = structure

    # Per-student overrides: a fee that's normally charged to the whole class
    # can be switched OFF for this one student (e.g. a returning student
    # skipping the "new student" registration fee), and a fee that's NOT
    # normally charged can be switched ON just for this student (e.g. one
    # student requesting an extra uniform set mid-term).
    exceptions = {
        exc.fee_structure_id: exc
        for exc in StudentFeeException.objects.filter(
            student=student, fee_structure_id__in=[s.pk for s in by_category.values()]
        )
    }

    for structure in by_category.values():
        exception = exceptions.get(structure.pk)

        if exception and exception.action == StudentFeeException.Action.EXCLUDE:
            # This student is explicitly opted out — make sure no stale line remains and skip.
            InvoiceItem.objects.filter(invoice=invoice, fee_structure=structure).delete()
            continue

        applies_to_student = structure.is_mandatory or (
            exception and exception.action == StudentFeeException.Action.INCLUDE
        )
        if not applies_to_student:
            # Optional fee that this student hasn't opted into — remove any stale line and skip.
            InvoiceItem.objects.filter(invoice=invoice, fee_structure=structure).delete()
            continue

        original_amount = structure.amount
        discount_rule, reduction = get_best_discount(
            student, structure.fee_category, term, session, original_amount
        )
        final_amount = original_amount - reduction

        InvoiceItem.objects.update_or_create(
            invoice=invoice, fee_category=structure.fee_category, fee_structure=structure,
            defaults={
                'description': structure.label or structure.fee_category.name,
                'original_amount': original_amount,
                'discount_amount': reduction,
                'applied_discount': discount_rule,
                'amount': final_amount,
                'quantity': 1,
            },
        )
        if structure.due_date and (not invoice.due_date or structure.due_date > invoice.due_date):
            invoice.due_date = structure.due_date

    for item in (extra_items or []):
        InvoiceItem.objects.create(
            invoice=invoice,
            fee_category=item['fee_category'],
            description=item.get('description', ''),
            amount=item['amount'],
            quantity=item.get('quantity', 1),
        )

    invoice.save()
    sync_invoice_status(invoice)
    # Explicit call, not just relying on the InvoiceItem post_save signal to
    # trigger this as a side-effect — if a student's fee structure produces
    # zero line items (e.g. nothing configured for their class yet), the
    # signal never fires at all and their ledger would otherwise never get
    # created. Calling it directly here guarantees a ledger row always
    # exists the moment an invoice is generated, regardless of how many
    # items ended up on it.
    sync_student_ledger(student, term, session)
    return invoice


@transaction.atomic
def bulk_generate_invoices(student_class, term, session, user=None, students_qs=None):
    """Generates invoices for every student in a class (or a custom queryset)."""
    from students.models import Student

    students = students_qs if students_qs is not None else Student.objects.filter(current_class=student_class)
    invoices = []
    for student in students:
        invoices.append(generate_invoice_for_student(student, term, session, user=user))
    return invoices


def sync_invoice_status(invoice):
    """Recomputes and persists an invoice's status from its totals."""
    balance = invoice.balance
    if invoice.status == Invoice.Status.CANCELLED:
        return invoice
    if balance <= ZERO and invoice.total_amount > ZERO:
        new_status = Invoice.Status.PAID
    elif invoice.total_paid > ZERO:
        new_status = Invoice.Status.PARTIAL
    elif invoice.is_overdue:
        new_status = Invoice.Status.OVERDUE
    else:
        new_status = Invoice.Status.ISSUED
    if new_status != invoice.status:
        invoice.status = new_status
        invoice.save(update_fields=['status'])
    return invoice


# ---------------------------------------------------------------------------
# Installment Plans
# ---------------------------------------------------------------------------
def build_equal_installments(invoice, count, due_dates=None, labels=None):
    """
    Splits an invoice's total amount into `count` equal tranches (the last
    one absorbs any rounding remainder so they always sum exactly to the
    invoice total), returning a list of dicts ready for
    ``create_installment_plan``. Does not touch the database.
    """
    if count < 1:
        raise ValueError("An installment plan needs at least 1 installment.")
    total = invoice.total_amount
    base = (total / count).quantize(Decimal('0.01'))
    installments, running_total = [], ZERO
    for i in range(count):
        is_last = (i == count - 1)
        amount = (total - running_total) if is_last else base
        running_total += amount
        installments.append({
            'label': labels[i] if labels and i < len(labels) else f"Installment {i + 1} of {count}",
            'amount_due': amount,
            'due_date': due_dates[i] if due_dates and i < len(due_dates) else None,
        })
    return installments


@transaction.atomic
def create_installment_plan(invoice, installments_data, user=None):
    """
    Creates (or replaces) an invoice's InstallmentPlan from a list of dicts:
        [{'label': '1st Installment', 'amount_due': Decimal('20000'), 'due_date': date(...)}, ...]

    Validates the tranches sum to the invoice's current total (to the
    penny) so the schedule can never silently under- or over-bill the
    parent relative to what's actually on the invoice.
    """
    total_scheduled = sum((Decimal(item['amount_due']) for item in installments_data), ZERO)
    if total_scheduled != invoice.total_amount:
        raise ValueError(
            f"Installments must add up to the invoice total ({invoice.total_amount}); "
            f"got {total_scheduled}."
        )

    plan, _created = InstallmentPlan.objects.update_or_create(invoice=invoice, defaults={'created_by': user})
    plan.installments.all().delete()
    for index, item in enumerate(installments_data, start=1):
        Installment.objects.create(
            plan=plan, sequence=index,
            label=item.get('label') or f"Installment {index}",
            amount_due=item['amount_due'], due_date=item.get('due_date'),
        )
    return plan


def get_installment_breakdown(plan):
    """
    Allocates the invoice's cumulative completed payments across its
    installments in sequence order (oldest first) — a FIFO "waterfall" —
    purely for display. Parents still just pay any amount against the
    invoice as usual; this function figures out which installment(s) that
    covers. Returns a list of dicts:
        {'installment', 'amount_due', 'amount_paid', 'balance', 'status', 'due_date'}
    where status is one of: paid, partial, overdue, pending.
    """
    remaining_paid = plan.invoice.total_paid
    today = timezone.localdate()
    breakdown = []

    for installment in plan.installments.order_by('sequence'):
        allocated = min(remaining_paid, installment.amount_due) if remaining_paid > ZERO else ZERO
        remaining_paid -= allocated
        balance = installment.amount_due - allocated

        if balance <= ZERO:
            status = 'paid'
        elif allocated > ZERO:
            status = 'partial'
        elif installment.due_date and today > installment.due_date:
            status = 'overdue'
        else:
            status = 'pending'

        breakdown.append({
            'installment': installment, 'amount_due': installment.amount_due,
            'amount_paid': allocated, 'balance': balance, 'status': status,
            'due_date': installment.due_date,
        })
    return breakdown


def get_next_due_installment(plan):
    """The first not-fully-paid installment in the plan, or None if it's fully settled."""
    for row in get_installment_breakdown(plan):
        if row['status'] != 'paid':
            return row
    return None


# ---------------------------------------------------------------------------
# Ledger sync
# ---------------------------------------------------------------------------
def sync_student_ledger(student, term, session):
    """Recalculates the cached StudentAccountLedger balance for a student/term/session."""
    total_invoiced = InvoiceItem.objects.filter(
        invoice__student=student, invoice__term=term, invoice__session=session,
    ).exclude(invoice__status=Invoice.Status.CANCELLED).aggregate(
        total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField())
    )['total']

    total_paid = Payment.objects.filter(
        student=student, term=term, session=session, status=Payment.Status.COMPLETED,
    ).aggregate(total=Coalesce(Sum('amount_received'), ZERO, output_field=DecimalField()))['total']

    balance = total_invoiced - total_paid

    ledger, _created = StudentAccountLedger.objects.update_or_create(
        student=student, term=term, session=session,
        defaults={'total_invoiced': total_invoiced, 'total_paid': total_paid, 'balance': balance},
    )
    return ledger


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
@transaction.atomic
def record_payment(*, user, student, amount_received, payment_method, payment_date=None,
                    invoice=None, fee_category=None, term=None, session=None,
                    transaction_id=None, notes='', discount_amount=ZERO, discount_percentage=ZERO,
                    status=Payment.Status.COMPLETED):
    """
    Central entry point for recording a payment (used by staff/parent forms,
    the admin, the API, and bulk "settle full balance" actions). Handles:
        - defaulting term/session/fee_category from the invoice,
        - generating a unique placeholder transaction id for manual/cash
          entries (avoids UNIQUE constraint clashes on blank references),
        - snapshotting the invoice balance before/after,
        - and (via the post_save signal) creating the Receipt and syncing
          the student's ledger.

    Returns the created Payment instance.
    """
    if invoice is not None:
        term = term or invoice.term
        session = session or invoice.session
        if fee_category is None:
            first_item = invoice.items.first()
            fee_category = first_item.fee_category if first_item else None

    # A payment that isn't tied to an invoice (a standalone/miscellaneous
    # payment, or an approved offline notification where staff didn't pick
    # an invoice) still needs a term/session to be filed under. Fall back
    # to whatever's currently marked as the active term/session rather
    # than leaving these blank — but never *guess* a fee category; that's
    # meaningful information a human should supply, not something safe to
    # invent silently.
    if term is None or session is None:
        current_term, current_session = get_current_term_session()
        term = term or current_term
        session = session or current_session

    missing = [name for name, value in
               [('fee_category', fee_category), ('term', term), ('session', session)] if value is None]
    if missing:
        raise ValueError(
            "Cannot record this payment - could not determine: " + ", ".join(missing) + ". "
            "Link it to an invoice (which supplies these automatically), pass them explicitly, "
            "or mark a current term/session under Curriculum settings."
        )

    if not transaction_id or not transaction_id.strip():
        transaction_id = f"MANUAL-{user.pk if user else 0}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
    else:
        transaction_id = transaction_id.strip()

    balance_before = invoice.balance if invoice else None

    payment = Payment.objects.create(
        student=student,
        invoice=invoice,
        fee_category=fee_category,
        term=term,
        session=session,
        amount_received=amount_received,
        discount_amount=discount_amount or ZERO,
        discount_percentage=discount_percentage or ZERO,
        payment_date=payment_date or timezone.localdate(),
        payment_method=payment_method,
        status=status,
        transaction_id=transaction_id,
        notes=notes,
        recorded_by=user,
        balance_before_payment=balance_before,
    )

    if invoice is not None and status == Payment.Status.COMPLETED:
        sync_invoice_status(invoice)
        payment.balance_after_payment = invoice.balance
        payment.save(update_fields=['balance_after_payment'])

    return payment


@transaction.atomic
def settle_invoice_balance(*, user, student, invoice, amount_received, payment_method,
                            payment_date=None, transaction_id=None, notes=''):
    """Convenience wrapper: pay down an invoice's outstanding balance directly."""
    if amount_received > invoice.balance:
        raise ValueError("Payment amount cannot exceed the outstanding invoice balance.")
    return record_payment(
        user=user, student=student, invoice=invoice, amount_received=amount_received,
        payment_method=payment_method, payment_date=payment_date,
        transaction_id=transaction_id, notes=notes,
    )


# ---------------------------------------------------------------------------
# Debtors
# ---------------------------------------------------------------------------
def get_debtors(term=None, session=None, student_class=None):
    """Returns a queryset-friendly list of ledgers where balance > 0."""
    qs = StudentAccountLedger.objects.select_related('student', 'term', 'session').filter(balance__gt=ZERO)
    if term:
        qs = qs.filter(term=term)
    if session:
        qs = qs.filter(session=session)
    if student_class:
        qs = qs.filter(student__current_class=student_class)
    return qs.order_by('-balance')


# ---------------------------------------------------------------------------
# Profit & Loss / Income statement
# ---------------------------------------------------------------------------
def get_income_breakdown(start_date=None, end_date=None, term=None, session=None):
    qs = Payment.objects.filter(status=Payment.Status.COMPLETED)
    if start_date:
        qs = qs.filter(payment_date__gte=start_date)
    if end_date:
        qs = qs.filter(payment_date__lte=end_date)
    if term:
        qs = qs.filter(term=term)
    if session:
        qs = qs.filter(session=session)

    breakdown = list(
        qs.values('fee_category__name').annotate(total=Sum('amount_received')).order_by('-total')
    )
    total_income = sum((row['total'] or ZERO for row in breakdown), ZERO)
    return breakdown, total_income


def get_expense_breakdown(start_date=None, end_date=None, term=None, session=None):
    qs = Expense.objects.exclude(status=Expense.Status.REJECTED)
    if start_date:
        qs = qs.filter(expense_date__gte=start_date)
    if end_date:
        qs = qs.filter(expense_date__lte=end_date)
    if term:
        qs = qs.filter(term=term)
    if session:
        qs = qs.filter(session=session)

    breakdown = list(
        qs.values('category__name').annotate(total=Sum('amount')).order_by('-total')
    )
    total_expense = sum((row['total'] or ZERO for row in breakdown), ZERO)
    return breakdown, total_expense


def get_profit_and_loss(start_date=None, end_date=None, term=None, session=None):
    """
    Returns a full Profit & Loss summary for the given period/term/session:
        {
            'income_breakdown': [...], 'total_income': Decimal,
            'expense_breakdown': [...], 'total_expense': Decimal,
            'net_profit': Decimal, 'margin_pct': Decimal,
            'period': {'start_date':..., 'end_date':..., 'term':..., 'session':...}
        }
    """
    income_breakdown, total_income = get_income_breakdown(start_date, end_date, term, session)
    expense_breakdown, total_expense = get_expense_breakdown(start_date, end_date, term, session)
    net_profit = total_income - total_expense
    margin_pct = (net_profit / total_income * Decimal('100')) if total_income else ZERO

    return {
        'income_breakdown': income_breakdown,
        'total_income': total_income,
        'expense_breakdown': expense_breakdown,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'margin_pct': margin_pct.quantize(Decimal('0.01')) if total_income else ZERO,
        'period': {
            'start_date': start_date, 'end_date': end_date,
            'term': term, 'session': session,
        },
    }


def get_dashboard_summary(term=None, session=None):
    """Snapshot figures for the Finance dashboard cards."""
    payments_qs = Payment.objects.filter(status=Payment.Status.COMPLETED)
    invoices_qs = Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
    expenses_qs = Expense.objects.exclude(status=Expense.Status.REJECTED)

    if term:
        payments_qs = payments_qs.filter(term=term)
        invoices_qs = invoices_qs.filter(term=term)
        expenses_qs = expenses_qs.filter(term=term)
    if session:
        payments_qs = payments_qs.filter(session=session)
        invoices_qs = invoices_qs.filter(session=session)
        expenses_qs = expenses_qs.filter(session=session)

    total_income = payments_qs.aggregate(total=Coalesce(Sum('amount_received'), ZERO,
                                                          output_field=DecimalField()))['total']
    total_expense = expenses_qs.aggregate(total=Coalesce(Sum('amount'), ZERO,
                                                           output_field=DecimalField()))['total']
    total_invoiced = InvoiceItem.objects.filter(invoice__in=invoices_qs).aggregate(
        total=Coalesce(Sum('amount'), ZERO, output_field=DecimalField()))['total']

    outstanding = total_invoiced - total_income
    debtor_count = get_debtors(term=term, session=session).count()

    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': total_income - total_expense,
        'total_invoiced': total_invoiced,
        'outstanding_balance': outstanding if outstanding > ZERO else ZERO,
        'debtor_count': debtor_count,
        'invoice_count': invoices_qs.count(),
        'payment_count': payments_qs.count(),
    }


# ---------------------------------------------------------------------------
# PDF rendering (shared by invoices, receipts, fee tables, and reports)
# ---------------------------------------------------------------------------
def render_to_pdf(template_src, context_dict=None, filename=None, as_attachment=False):
    """
    Renders an HTML template to a PDF HttpResponse using xhtml2pdf.
    Falls back gracefully (returns None) if rendering fails so the calling
    view can show a friendly error instead of a 500.
    """
    from xhtml2pdf import pisa

    context_dict = context_dict or {}
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()

    def link_callback(uri, rel):
        if uri.startswith(settings.STATIC_URL):
            path = os.path.join(settings.STATIC_ROOT or '', uri.replace(settings.STATIC_URL, ""))
        elif settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT or '', uri.replace(settings.MEDIA_URL, ""))
        else:
            path = os.path.join(settings.BASE_DIR, uri.lstrip('/'))
        return path

    pdf = pisa.CreatePDF(html, dest=result, link_callback=link_callback)
    if pdf.err:
        return None

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    if filename:
        disposition = 'attachment' if as_attachment else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response
