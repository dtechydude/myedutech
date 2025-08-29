# student_management_app/models.py (or payments/models.py if you create a new app)

from django.db import models
from django.contrib.auth.models import User # Assuming User model for staff/admins
from students.models import Student # Assuming you have a Student model in a 'students' app
from decimal import Decimal # Import Decimal for precise calculations
from django.utils import timezone # Import timezone
from django.db.models import Sum # Import Sum for aggregation
from curriculum.models import Term, Session, Standard
from django.conf import settings

# Assuming you have Term and Session models already defined.
class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')

    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        # unique_together = ['acc_number', 'bank_name']


class PaymentCategory(models.Model):
    """
    Defines different categories for student payments (e.g., Tuition, Hostel, Exam Fees).
    """
    name = models.CharField(max_length=100, unique=True,
                            help_text="Name of the payment category (e.g., 'Tuition Fee JSS1', 'Hostel Fee JSS2').")
    description = models.TextField(blank=True, null=True,
                                   help_text="A brief description of the payment category.")

    class Meta:
        verbose_name = "Payment Category"
        verbose_name_plural = "Payment Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class CategoryFee(models.Model):
    """
    Defines the standard amount due for a specific payment category, term, and session.
    This will be used to automatically populate the 'original_amount' for student payments.
    """
    student_class = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='fees', null=True, blank=True, 
                                      help_text="The class level this fee applies to.")
    payment_category = models.ForeignKey(PaymentCategory, on_delete=models.CASCADE, related_name='fees',
                                         help_text="The payment category this fee applies to.")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='category_fees',
                             help_text="The academic term this fee applies to.")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='category_fees',
                                help_text="The academic session this fee applies to.")
    fee_name = models.CharField(max_length=255, blank=True, null=True,
                                help_text="A specific name for this fee instance (e.g., 'First Semester Tuition').") # New field
    amount_due = models.DecimalField(max_digits=10, decimal_places=2,
                                     help_text="The standard amount due for this category, term, and session.")

    class Meta:
        unique_together = ('payment_category', 'term', 'session', 'student_class', 'fee_name') # Added fee_name to unique_together
        verbose_name = "Category Fee"
        verbose_name_plural = "Category Fees"
        ordering = ['session__name', 'term__name', 'payment_category__name', 'fee_name'] # Added fee_name to ordering

    def __str__(self):
        # Updated to include fee_name if available
        if self.fee_name:
            return f"{self.fee_name} ({self.payment_category.name}) for {self.term.name} ({self.session.name}): N{self.amount_due}"
        return f"{self.payment_category.name} for {self.term.name} ({self.session.name}): N{self.amount_due}"


class StudentAccountLedger(models.Model):
    """
    Tracks the financial balance (debit/credit) for a student for a specific term and session.
    A positive 'balance' means the student owes money (debtor).
    A negative 'balance' means the student has a credit.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='account_ledgers',
                                help_text="The student whose account balance is being tracked.")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='student_ledgers',
                             help_text="The academic term for this balance.")
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='student_ledgers',
                                help_text="The academic session for this balance.")
    # 'balance' represents the net amount owed (positive) or credit (negative)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                  help_text="The current balance for the student in this term/session. Positive for debit, negative for credit.")
    last_updated = models.DateTimeField(auto_now=True,
                                        help_text="The last time this ledger entry was updated.")

    class Meta:
        unique_together = ('student', 'term', 'session') # A student can only have one ledger entry per term/session
        verbose_name = "Student Account Ledger"
        verbose_name_plural = "Student Account Ledgers"
        ordering = ['student__last_name', 'session__name', 'term__name']

    def __str__(self):
        status = "owing" if self.balance > 0 else "in credit" if self.balance < 0 else "balanced"
        return f"{self.student.first_name} {self.student.last_name} ({self.term} - {self.session}): {self.balance} {status}"


class Payment(models.Model):
    """
    Represents a payment made by or for a student.
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Card Payment'),
        ('online_gateway', 'Online Gateway'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments',
                                help_text="The student associated with this payment.")
    original_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                          blank=True, null=True,
                                          help_text="The original amount due for this payment (can be derived from Category Fee or manually set).")
    amount_received = models.DecimalField(max_digits=10, decimal_places=2,
                                          help_text="The actual amount received in this payment transaction.")

    payment_date = models.DateTimeField(auto_now_add=True,
                                        help_text="The date and time the payment was recorded.")
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending',
                              help_text="The current status of the payment (e.g., completed, pending).")
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES,
                                      help_text="The method used for the payment.")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True,
                                      help_text="Unique ID from payment gateway or internal transaction ID.")
    notes = models.CharField(max_length=100, blank=True, null=True,
                              help_text="Any additional notes or remarks about the payment.")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="The staff member who recorded this payment.")

    # Fields for categorization and installments
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='payments',
                             help_text="The academic term this payment is for.")
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='payments',
                                 help_text="The academic session this payment is for.")
    payment_category = models.ForeignKey(PaymentCategory, on_delete=models.PROTECT, related_name='payments',
                                          help_text="The category of this payment (e.g., Tuition, Hostel).")

    is_installment = models.BooleanField(default=False,
                                         help_text="Check if this payment is part of an installment plan.")
    installment_number = models.PositiveIntegerField(blank=True, null=True,
                                                     help_text="The current installment number (e.g., 1st, 2nd).")
    total_installments = models.PositiveIntegerField(blank=True, null=True,
                                                     help_text="The total number of installments for this payment plan.")

    # Fields for discount
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                          help_text="Fixed discount amount applied to the payment.")
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                              help_text="Percentage discount applied to the payment (e.g., 10.00 for 10%).")

    # New fields to capture balance related to the specific CategoryFee at the time of payment
    balance_before_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                 help_text="Balance remaining for this specific CategoryFee before this payment.")
    balance_after_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                help_text="Balance remaining for this specific CategoryFee after this payment.")
    
    confirm_payment = models.BooleanField(default=False, verbose_name='confirm the payment')

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment of {self.amount_received} for {self.student.first_name} {self.student.last_name} ({self.payment_category}) for {self.term} - {self.session}"

    @property
    def net_amount_due(self):
        """Calculates the net amount due for this payment record after applying discounts."""
        base_amount = self.original_amount if self.original_amount is not None else Decimal('0.00')

        calculated_amount = base_amount
        if self.discount_percentage > 0:
            calculated_amount -= (base_amount * (self.discount_percentage / Decimal('100.00')))
        if self.discount_amount > 0:
            calculated_amount -= self.discount_amount
        return max(Decimal('0.00'), calculated_amount)

    def save(self, *args, **kwargs):
        """
        Overrides the save method to:
        1. Populate original_amount from the related StudentFee record (on creation only).
        2. Correctly calculate balances based on a single StudentFee record.
        3. Automatically set the installment_number and total_installments.
        """
        # Step 1: Populate original_amount from the StudentFee model
        # This should only happen for new records.
        if not self.pk:
            try:
                student_fee = StudentFee.objects.get(
                    student=self.student,
                    category_fee__payment_category=self.payment_category,
                    term=self.term,
                    session=self.session
                )
                self.original_amount = student_fee.amount_due
            except StudentFee.DoesNotExist:
                self.original_amount = Decimal('0.00')

        # Step 2: Calculate balances for the specific category/term/session
        try:
            student_fee_record = StudentFee.objects.get(
                student=self.student,
                category_fee__payment_category=self.payment_category,
                term=self.term,
                session=self.session
            )
            total_charges_for_category = student_fee_record.amount_due
        except StudentFee.DoesNotExist:
            total_charges_for_category = Decimal('0.00')

        total_paid_for_category_before = Payment.objects.filter(
            student=self.student,
            payment_category=self.payment_category,
            term=self.term,
            session=self.session,
            status='completed'
        ).exclude(pk=self.pk).aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')

        self.balance_before_payment = total_charges_for_category - total_paid_for_category_before
        self.balance_before_payment = max(Decimal('0.00'), self.balance_before_payment)

        self.balance_after_payment = self.balance_before_payment - self.amount_received
        self.balance_after_payment = max(Decimal('0.00'), self.balance_after_payment)

        # Step 3: Automatically set the installment number and total_installments
        if self.is_installment:
            # Calculate the current installment number
            if self.installment_number is None:
                previous_installments = Payment.objects.filter(
                    student=self.student,
                    payment_category=self.payment_category,
                    term=self.term,
                    session=self.session,
                    is_installment=True,
                    status='completed'
                ).count()
                self.installment_number = previous_installments + 1

            # Get the total installments from a previous payment if it exists
            if not self.total_installments:
                last_installment = Payment.objects.filter(
                    student=self.student,
                    payment_category=self.payment_category,
                    term=self.term,
                    session=self.session,
                    is_installment=True
                ).order_by('-payment_date').first()
                
                if last_installment and last_installment.total_installments:
                    self.total_installments = last_installment.total_installments

        super().save(*args, **kwargs)

        # Step 4: Update the StudentAccountLedger
        if self.status == 'completed' and self.student and self.term and self.session:
            total_charges_for_period = StudentFee.objects.filter(
                student=self.student,
                term=self.term,
                session=self.session
            ).aggregate(Sum('amount_due'))['amount_due__sum'] or Decimal('0.00')

            total_payments_for_period = Payment.objects.filter(
                student=self.student,
                term=self.term,
                session=self.session,
                status='completed'
            ).aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')
            
            ledger_entry, created = StudentAccountLedger.objects.get_or_create(
                student=self.student,
                term=self.term,
                session=self.session,
                defaults={'balance': Decimal('0.00')}
            )
            ledger_entry.balance = total_charges_for_period - total_payments_for_period
            ledger_entry.save()



class Receipt(models.Model):
    """
    Represents a payment receipt generated after a successful payment.
    """
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='receipt',
                                   help_text="The payment associated with this receipt.")
    receipt_number = models.CharField(max_length=50, unique=True,
                                      help_text="A unique identifier for the receipt.")
    issue_date = models.DateTimeField(auto_now_add=True,
                                      help_text="The date and time the receipt was issued.")
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text="The staff member who generated this receipt.")
    # You might want to add a field for a PDF file if you generate physical PDFs
    # pdf_file = models.FileField(upload_to='receipts/pdfs/', blank=True, null=True)

    class Meta:
        ordering = ['-issue_date']
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"

    def save(self, *args, **kwargs):
        """
        Overrides the save method to generate a unique receipt number if not provided.
        Ensures issue_date is set before calling strftime.
        """
        # Call original save first to ensure self.pk and self.issue_date are set for new objects
        is_new = not self.pk
        super().save(*args, **kwargs) # This will set self.pk and self.issue_date for new objects

        # Generate receipt_number only if it's a new object and not already set
        if is_new and not self.receipt_number:
            # issue_date should now be populated by auto_now_add. If not, set it as fallback.
            if not self.issue_date:
                self.issue_date = timezone.now()

            today_str = self.issue_date.strftime('%Y%m%d')
            last_receipt = Receipt.objects.filter(receipt_number__startswith=f"REC-{today_str}-").order_by('receipt_number').last()
            if last_receipt:
                try:
                    last_id_part = int(last_receipt.receipt_number.split('-')[-1])
                    new_id_part = last_id_part + 1
                except ValueError:
                    new_id_part = 1
            else:
                new_id_part = 1
            self.receipt_number = f"REC-{today_str}-{new_id_part:04d}"
            # Save again to update the receipt_number field.
            # Use update_fields to prevent infinite recursion and only update this specific field.
            super().save(update_fields=['receipt_number'])


# helping to calculate the debtors accurately
class StudentFee(models.Model):
    """
    Represents a fee specifically assigned to a student for a given term/session.
    The amount can be different from the standard CategoryFee amount.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='student_fees')
    category_fee = models.ForeignKey(CategoryFee, on_delete=models.CASCADE, related_name='student_fees', 
                                    help_text="The standard fee category this student's fee is based on.")
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='student_fees')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='student_fees')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2,
                                     help_text="The actual amount this specific student owes.")
    
    class Meta:
        unique_together = ('student', 'category_fee', 'term', 'session')
        verbose_name = "Student Fee"
        verbose_name_plural = "Student Fees"

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.category_fee.payment_category.name} ({self.amount_due})"
