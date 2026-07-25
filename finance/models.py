# finance/models.py
"""
Finance app models for KwikSchools.

Covers:
    - Bank Accounts
    - Fee Categories & Fee Structures (class/term/session based fee setup)
    - Invoices & Invoice Line Items (formal, printable invoicing)
    - Payments & Receipts (with auto numbering)
    - Student Ledger (running, auditable balance history)
    - Payment Notifications (offline payment proof submission)
    - Expense Categories, Vendors & Expenses (expenditure tracking)

Design notes:
    - Heavy business logic (invoice generation, payment recording, ledger
      sync, profit & loss computation) lives in ``finance/services.py`` so
      that models stay thin, testable, and reusable from the admin, views,
      the REST API, and management commands alike.
    - Sequential, human-friendly document numbers (invoice/receipt) are
      generated through ``finance.services.generate_document_number`` and
      assigned in ``finance/signals.py`` right after the object is first
      created, avoiding duplicated numbering logic across the codebase.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from curriculum.models import Term, Session, Standard
from students.models import Student

User = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------------------
# Shared choice sets
# ---------------------------------------------------------------------------
class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
    CARD = 'card', 'Card Payment'
    ONLINE_GATEWAY = 'online_gateway', 'Online Gateway'
    CHEQUE = 'cheque', 'Cheque'
    MOBILE_MONEY = 'mobile_money', 'Mobile Money'
    POS = 'pos', 'POS Terminal'


# ---------------------------------------------------------------------------
# Bank Accounts
# ---------------------------------------------------------------------------
class BankAccount(models.Model):
    """A school bank account that fee payers can pay into."""
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100, verbose_name='Bank Name')
    branch = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False, help_text="Show this account first on invoices/receipts.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_primary', 'bank_name']
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"

    def __str__(self):
        return f'{self.bank_name} - {self.account_number} ({self.account_name})'


# ---------------------------------------------------------------------------
# Fee Categories & Fee Structure (class/term/session based fee setup)
# ---------------------------------------------------------------------------
class FeeCategory(models.Model):
    """A billable fee type, e.g. Tuition, Hostel, Transport, Exam, Uniform."""

    class CategoryType(models.TextChoices):
        TUITION = 'tuition', 'Tuition'
        HOSTEL = 'hostel', 'Hostel / Boarding'
        TRANSPORT = 'transport', 'Transport'
        EXAM = 'exam', 'Examination'
        UNIFORM = 'uniform', 'Uniform & Wears'
        BOOKS = 'books', 'Books & Learning Materials'
        FEEDING = 'feeding', 'Feeding'
        PTA = 'pta', 'PTA / Development Levy'
        ADMISSION = 'admission', 'Admission / Registration'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=100, unique=True,
                             help_text="e.g. 'Tuition Fee', 'Hostel Fee', 'Bus Fee - Zone A'.")
    category_type = models.CharField(max_length=20, choices=CategoryType.choices, default=CategoryType.OTHER,
                                      help_text="Used to group income for reporting and P&L breakdowns.")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Category"
        verbose_name_plural = "Fee Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    """
    The standard fee amount for a category, applicable to a class (or all
    classes, if left blank), for a given term/session. Used to auto-generate
    student invoices — this is the single source of truth for "how much
    should a JSS1 student pay for Tuition this term".
    """
    student_class = models.ForeignKey(
        Standard, on_delete=models.CASCADE, related_name='fin_fee_structures', null=True, blank=True,
        help_text="Leave blank to apply this fee to ALL classes (e.g. a school-wide PTA levy)."
    )
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE, related_name='fee_structures')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='fin_fee_structures')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='fin_fee_structures')
    label = models.CharField(max_length=255, blank=True,
                              help_text="Optional specific label, e.g. 'First Term Tuition - Boarding'.")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    is_mandatory = models.BooleanField(default=True, help_text="Uncheck for optional charges (e.g. extra lessons).")
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('student_class', 'fee_category', 'term', 'session', 'label')
        verbose_name = "Fee Structure"
        verbose_name_plural = "Fee Structures"
        ordering = ['session__name', 'term__name', 'student_class__name', 'fee_category__name']

    def __str__(self):
        cls = self.student_class.name if self.student_class else 'All Classes'
        label = f" ({self.label})" if self.label else ""
        return f"{cls} - {self.fee_category.name}{label} | {self.term.name} {self.session.name}: {self.amount}"


class StudentFeeException(models.Model):
    """
    Flips whether a specific FeeStructure line applies to one particular
    student — independent of what every other student in the same class
    is being charged. Two situations this is for:

        - EXCLUDE: the fee is normally charged to everyone in the class
          (FeeStructure.is_mandatory=True) but this one student shouldn't
          pay it — e.g. a returning student is excluded from the JSS1
          "New Student Registration Fee" that the rest of the intake pays.

        - INCLUDE: the fee is NOT normally charged (FeeStructure.
          is_mandatory=False — an optional add-on like "Uniform - Extra
          Set") but this one student specifically requested/qualifies for
          it — e.g. one student asks for an extra uniform mid-term; only
          their invoice gets the line, nobody else's.

    Only one exception can exist per (student, fee_structure) pair — a
    fee is either switched on or off for that student, not both.
    """

    class Action(models.TextChoices):
        EXCLUDE = 'exclude', 'Exclude (do not charge this student)'
        INCLUDE = 'include', 'Include (charge this student even though it is optional/not default)'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_fee_exceptions')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='student_exceptions')
    action = models.CharField(max_length=10, choices=Action.choices)
    reason = models.CharField(max_length=255, help_text="e.g. 'Returning student — registration fee waived', "
                                                          "'Requested extra uniform set, Term 2'.")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='fin_fee_exceptions_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'fee_structure')
        verbose_name = "Student Fee Exception"
        verbose_name_plural = "Student Fee Exceptions"
        ordering = ['student__last_name', '-created_at']

    def __str__(self):
        return f"{self.get_action_display()}: {self.student.get_full_name()} — {self.fee_structure}"


class StudentDiscount(models.Model):
    """
    A concession/scholarship/reduction granted to an individual student —
    e.g. a sibling discount, a staff-ward waiver, or a merit scholarship.
    Applied automatically whenever an invoice is (re)generated for that
    student, so two students in the same class can legitimately owe
    different amounts for the same fee category.

    Leaving fee_category/term/session blank makes the discount broader:
        - fee_category blank  -> applies to every fee category on the invoice
        - term blank          -> applies every term
        - session blank       -> applies every session (a standing waiver)
    A fully blank scope (all three blank) is a blanket "X% off everything,
    forever" discount — typical for a staff-ward policy.

    If a student qualifies for more than one matching discount on a given
    line, the single LARGEST reduction is applied (discounts don't stack)
    — this matches how most schools actually apply concessions and avoids
    surprise 100%+ waivers from combining unrelated policies.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage Off'
        FIXED = 'fixed', 'Fixed Amount Off'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_discounts')
    fee_category = models.ForeignKey(
        FeeCategory, on_delete=models.CASCADE, null=True, blank=True, related_name='discounts',
        help_text="Leave blank to apply this discount to ALL fee categories on the student's invoice."
    )
    term = models.ForeignKey(Term, on_delete=models.CASCADE, null=True, blank=True, related_name='fin_discounts',
                              help_text="Leave blank to apply every term.")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True, related_name='fin_discounts',
                                 help_text="Leave blank to apply every session (a standing waiver).")
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    value = models.DecimalField(max_digits=8, decimal_places=2,
                                 help_text="e.g. 20 for 20% off, or a fixed Naira amount off, depending on type.")
    reason = models.CharField(max_length=255, help_text="e.g. 'Sibling discount', 'Staff ward', "
                                                          "'Merit scholarship - 100%'.")
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='fin_discounts_approved')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Student Discount / Concession"
        verbose_name_plural = "Student Discounts / Concessions"
        ordering = ['student__last_name', '-created_at']
        permissions = [
            ('manage_discounts', 'Can grant or revoke student fee discounts'),
        ]

    def __str__(self):
        scope = self.fee_category.name if self.fee_category else 'All Categories'
        value_display = f"{self.value}%" if self.discount_type == self.DiscountType.PERCENTAGE else f"{self.value}"
        return f"{self.student.get_full_name()} — {value_display} off {scope} ({self.reason})"

    def matches(self, fee_category, term, session):
        """Whether this discount rule applies to a given invoice line's scope."""
        if self.fee_category_id and self.fee_category_id != fee_category.id:
            return False
        if self.term_id and self.term_id != term.id:
            return False
        if self.session_id and self.session_id != session.id:
            return False
        return self.is_active

    def reduction_for(self, original_amount):
        """The Naira amount this rule would knock off a given original amount."""
        if self.discount_type == self.DiscountType.PERCENTAGE:
            reduction = (self.value / Decimal('100.00')) * original_amount
        else:
            reduction = self.value
        return min(reduction, original_amount)


# ---------------------------------------------------------------------------
# Invoicing
# ---------------------------------------------------------------------------
class Invoice(models.Model):
    """
    A formal, printable invoice issued to a student for a given term/session,
    made up of one or more InvoiceItem line items. Replaces the old implicit
    "StudentFeeAssignment" totals with an explicit, exportable document.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ISSUED = 'issued', 'Issued'
        PARTIAL = 'partial', 'Partially Paid'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_invoices')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='fin_invoices')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='fin_invoices')
    invoice_number = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ISSUED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='fin_invoices_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'term', 'session')
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ['-issue_date', '-id']
        permissions = [
            ('generate_invoices', 'Can bulk-generate invoices for a class'),
            ('view_profit_loss', 'Can view Profit & Loss reports'),
            ('export_financial_reports', 'Can export financial reports (PDF/CSV)'),
        ]


    def __str__(self):
        return f"{self.invoice_number or 'DRAFT'} - {self.student.get_full_name()} ({self.term} {self.session})"

    def get_absolute_url(self):
        return reverse('finance:invoice_detail', args=[self.pk])

    # -- Computed totals -----------------------------------------------
    @property
    def subtotal(self):
        return self.items.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def total_amount(self):
        return self.subtotal

    @property
    def total_paid(self):
        return self.payments.filter(status='completed').aggregate(
            total=models.Sum('amount_received'))['total'] or Decimal('0.00')

    @property
    def balance(self):
        return self.total_amount - self.total_paid

    @property
    def is_paid(self):
        return self.balance <= Decimal('0.00') and self.total_amount > Decimal('0.00')

    @property
    def is_overdue(self):
        return bool(self.due_date) and self.balance > 0 and timezone.localdate() > self.due_date


class InvoiceItem(models.Model):
    """A single billable line on an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name='invoice_items')
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='invoice_items')
    description = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    original_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="The undiscounted fee-structure amount, before any StudentDiscount was applied."
    )
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Total concession/scholarship reduction applied to this line."
    )
    applied_discount = models.ForeignKey(
        'StudentDiscount', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items',
        help_text="The discount rule that produced discount_amount, if any (for audit trail)."
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))],
                                  help_text="Final payable line total (already net of any discount).")

    class Meta:
        verbose_name = "Invoice Item"
        verbose_name_plural = "Invoice Items"
        ordering = ['fee_category__name']

    def __str__(self):
        label = self.description or self.fee_category.name
        return f"{label}: {self.amount}"


# ---------------------------------------------------------------------------
# Installment Plans
# ---------------------------------------------------------------------------
class InstallmentPlan(models.Model):
    """
    An optional, structured payment schedule for an Invoice — e.g. "60% by
    resumption, 40% by mid-term" or "3 equal installments, due monthly".

    Deliberately does NOT link individual Payment rows to individual
    Installment rows — a parent just pays whatever they have against the
    invoice as usual (staff-recorded, self-service, or via a verified bank
    transfer notification, same as any other payment). Instead, the
    invoice's cumulative amount paid is allocated across installments in
    order (oldest first) purely for *display* — see
    ``services.get_installment_breakdown()``. This keeps the payment flow
    identical to a non-installment invoice while still showing "installment
    2 of 3 is overdue" to staff and parents.
    """
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='installment_plan')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='fin_installment_plans_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Installment Plan"
        verbose_name_plural = "Installment Plans"

    def __str__(self):
        return f"Installment plan for {self.invoice.invoice_number}"


class Installment(models.Model):
    """A single scheduled tranche within an InstallmentPlan."""
    plan = models.ForeignKey(InstallmentPlan, on_delete=models.CASCADE, related_name='installments')
    sequence = models.PositiveSmallIntegerField(help_text="Order of this installment, e.g. 1, 2, 3.")
    label = models.CharField(max_length=100, help_text="e.g. '1st Installment', 'Resumption Payment'.")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2,
                                      validators=[MinValueValidator(Decimal('0.01'))])
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('plan', 'sequence')
        ordering = ['plan', 'sequence']
        verbose_name = "Installment"
        verbose_name_plural = "Installments"

    def __str__(self):
        return f"{self.label} — {self.amount_due} due {self.due_date or 'anytime'}"


# ---------------------------------------------------------------------------
# Payments & Receipts
# ---------------------------------------------------------------------------
class Payment(models.Model):
    """A payment made by/for a student, optionally tied to an Invoice."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_payments')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments',
                                 help_text="The invoice this payment is settling. Leave blank for a misc. payment.")
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name='payments',
                                      help_text="Category this payment is recorded under (auto-filled from invoice "
                                                "if left blank).")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='fin_payments')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='fin_payments')

    amount_received = models.DecimalField(max_digits=12, decimal_places=2,
                                           validators=[MinValueValidator(Decimal('0.01'))])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    payment_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    transaction_id = models.CharField(max_length=100, blank=True, null=True,
                                       help_text="Gateway/bank reference. Auto-generated for manual/cash entries.")
    notes = models.CharField(max_length=255, blank=True)

    balance_before_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance_after_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='fin_payments_recorded')
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-id']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=['student', 'term', 'session']),
            models.Index(fields=['status', 'payment_date']),
        ]

    def __str__(self):
        return f"{self.amount_received} from {self.student.get_full_name()} ({self.payment_category_display})"

    @property
    def payment_category_display(self):
        return self.fee_category.name if self.fee_category_id else "General"

    @property
    def net_amount(self):
        """Amount received, net of any recorded discount (for reporting)."""
        pct_discount = (self.discount_percentage / Decimal('100.00')) * self.amount_received \
            if self.discount_percentage else Decimal('0.00')
        return self.amount_received - self.discount_amount - pct_discount


class Receipt(models.Model):
    """Auto-generated printable receipt for a completed payment."""
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt')
    receipt_number = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    issue_date = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='fin_receipts_generated')

    class Meta:
        ordering = ['-issue_date']
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"

    def __str__(self):
        return f"Receipt #{self.receipt_number} for {self.payment.student}"

    def get_absolute_url(self):
        return reverse('finance:receipt_detail', args=[self.pk])


# ---------------------------------------------------------------------------
# Student Ledger (auditable running balance)
# ---------------------------------------------------------------------------
class StudentAccountLedger(models.Model):
    """
    Cached current balance for a student for a term/session, for fast
    dashboard/debtor lookups. Kept in sync by finance.signals whenever an
    Invoice, InvoiceItem, or Payment changes. Positive balance = student owes.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_account_ledgers')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='fin_student_ledgers')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='fin_student_ledgers')
    total_invoiced = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'term', 'session')
        verbose_name = "Student Account Ledger"
        verbose_name_plural = "Student Account Ledgers"
        ordering = ['student__last_name', 'session__name', 'term__name']

    def __str__(self):
        status = "owing" if self.balance > 0 else "in credit" if self.balance < 0 else "settled"
        return f"{self.student.get_full_name()} ({self.term} {self.session}): {self.balance} ({status})"


class StudentLedgerEntry(models.Model):
    """
    An immutable, auditable transaction log entry (debit = charge raised,
    credit = payment received) backing the cached StudentAccountLedger.
    """

    class EntryType(models.TextChoices):
        DEBIT = 'debit', 'Debit (Charge)'
        CREDIT = 'credit', 'Credit (Payment)'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_ledger_entries')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='fin_ledger_entries')
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='fin_ledger_entries')
    entry_type = models.CharField(max_length=12, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='ledger_entries')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='ledger_entries')
    running_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['student', '-created_at']
        verbose_name = "Student Ledger Entry"
        verbose_name_plural = "Student Ledger Entries"

    def __str__(self):
        return f"{self.get_entry_type_display()} of {self.amount} for {self.student.get_full_name()}"


# ---------------------------------------------------------------------------
# Offline Payment Notifications
# ---------------------------------------------------------------------------
class PaymentNotification(models.Model):
    """A parent/student declares an offline payment for staff to verify."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        PROCESSED = 'PROCESSED', 'Processed (Payment Recorded)'
        REJECTED = 'REJECTED', 'Rejected (Invalid Proof)'

    class Method(models.TextChoices):
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CASH_DEPOSIT = 'CASH_DEPOSIT', 'Cash Deposit (Bank)'
        POS = 'POS', 'POS Transaction'
        CHEQUE = 'CHEQUE', 'Cheque'
        OTHER = 'OTHER', 'Other Offline Method'

    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT, null=True, blank=True,
                                      verbose_name="School Bank Account")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fin_payment_notifications',
                                 verbose_name="Student Paid For")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=Method.choices, default=Method.BANK_TRANSFER)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateField(default=timezone.localdate)
    proof_of_payment = models.FileField(
        upload_to='finance/payment_proofs/%Y/%m/', blank=True, null=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Upload a screenshot/scan of the payment evidence (PDF, JPG or PNG)."
    )

    session = models.ForeignKey(Session, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='fin_payment_notifications')
    term = models.ForeignKey(Term, on_delete=models.PROTECT, null=True, blank=True,
                              related_name='fin_payment_notifications')

    notified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='fin_payment_notifications_sent')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    submission_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='fin_payment_notifications_processed')
    processed_at = models.DateTimeField(null=True, blank=True)
    resulting_payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True,
                                              related_name='source_notification')

    class Meta:
        verbose_name = "Payment Notification"
        verbose_name_plural = "Payment Notifications"
        ordering = ['-submission_date']

    def __str__(self):
        return f"Notification: {self.student} - {self.amount_paid} ({self.status})"


# ---------------------------------------------------------------------------
# Expense Tracking
# ---------------------------------------------------------------------------
class ExpenseCategory(models.Model):
    """Groups expenditure for reporting, e.g. Salaries, Utilities, Maintenance."""

    class CategoryType(models.TextChoices):
        SALARIES = 'salaries', 'Staff Salaries & Wages'
        UTILITIES = 'utilities', 'Utilities (Power, Water, Internet)'
        MAINTENANCE = 'maintenance', 'Repairs & Maintenance'
        SUPPLIES = 'supplies', 'Teaching & Office Supplies'
        TRANSPORT = 'transport', 'Transport & Fuel'
        FOOD = 'food', 'Feeding / Catering'
        MARKETING = 'marketing', 'Marketing & Admissions'
        ADMIN = 'admin', 'Administrative'
        CAPITAL = 'capital', 'Capital Expenditure (Assets)'
        TAX = 'tax', 'Taxes & Levies'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=100, unique=True)
    category_type = models.CharField(max_length=20, choices=CategoryType.choices, default=CategoryType.OTHER)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Expense Category"
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Vendor(models.Model):
    """A supplier/vendor/payee that the school pays money to."""
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Vendor / Payee"
        verbose_name_plural = "Vendors / Payees"

    def __str__(self):
        return self.name


class Expense(models.Model):
    """A single school expenditure record, for expense tracking & P&L."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        PAID = 'paid', 'Paid'
        REJECTED = 'rejected', 'Rejected'

    title = models.CharField(max_length=200, help_text="Short description, e.g. 'July diesel purchase'.")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    expense_date = models.DateField(default=timezone.localdate)
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name='fin_expenses')
    session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name='fin_expenses')
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference_number = models.CharField(max_length=100, blank=True, help_text="Cheque no. / transfer ref, etc.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PAID)
    attachment = models.FileField(
        upload_to='finance/expense_receipts/%Y/%m/', blank=True, null=True,
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])],
        help_text="Optional receipt/invoice from the vendor (PDF, JPG or PNG)."
    )
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='fin_expenses_recorded')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='fin_expenses_approved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-id']
        verbose_name = "Expense"
        verbose_name_plural = "Expenses"
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['category', 'expense_date']),
        ]
        permissions = [
            ('approve_expense', 'Can approve or reject expenses'),
        ]


    def __str__(self):
        return f"{self.title} - {self.amount} ({self.expense_date})"
