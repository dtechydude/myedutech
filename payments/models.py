# student_management_app/models.py (or payments/models.py if you create a new app)

from django.db import models
from django.contrib.auth.models import User # Assuming User model for staff/admins
from students.models import Student # Assuming you have a Student model in a 'students' app
from decimal import Decimal # Import Decimal for precise calculations
from django.utils import timezone # Import timezone
from django.db.models import Sum # Import Sum for aggregation
from curriculum.models import Term, Session, Standard
from django.conf import settings
from .utils import update_student_ledger # This import is fine
from django.contrib.auth import get_user_model

# Assuming you have Term and Session models already defined.
class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')
    description = models.CharField(max_length=50, blank=False, verbose_name='Description')


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


# STUDENT ACCOUNT LEDGER
# Get the User model dynamically
User = get_user_model()

# Student Account Ledger
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
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                  help_text="The current balance for the student in this term/session. Positive for debit, negative for credit.")
    last_updated = models.DateTimeField(auto_now=True,
                                        help_text="The last time this ledger entry was updated.")

    class Meta:
        unique_together = ('student', 'term', 'session')
        verbose_name = "Student Account Ledger"
        verbose_name_plural = "Student Account Ledgers"
        ordering = ['student__last_name', 'session__name', 'term__name']

    def __str__(self):
        status = "owing" if self.balance > 0 else "in credit" if self.balance < 0 else "balanced"
        return f"{self.student.first_name} {self.student.last_name} ({self.term} - {self.session}): {self.balance} {status}"


# THE PAYMENT MODEL
# Payment
# Payment Model
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
    
    student_fee_assignment = models.ForeignKey(
        'StudentFeeAssignment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='payments', 
        help_text="The specific fee assignment this payment applies to."
    )

    original_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                         blank=True, null=True,
                                         help_text="The total invoice amount due before this payment.")
    
    amount_received = models.DecimalField(max_digits=10, decimal_places=2,
                                         help_text="The actual amount received in this payment transaction.")
    
    payment_date = models.DateField(blank=True, null=True,
        help_text="The date the payment was made by the student."
    )
    
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending',
                             help_text="The current status of the payment.")
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES,
                                      help_text="The method used for the payment.")
    
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=False,
                                      help_text="Unique ID from payment gateway or internal transaction ID.")
    
    notes = models.CharField(max_length=100, blank=True, null=True,
                             help_text="Any additional notes or remarks about the payment.")
    
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="The staff member who recorded this payment.")

    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='payments',
                             help_text="The academic term this payment is for.")
                             
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name='payments',
                                help_text="The academic session this payment is for.")
                                
    payment_category = models.ForeignKey(PaymentCategory, on_delete=models.PROTECT, related_name='payments',
                                         help_text="The category of this payment (e.g., Tuition, Hostel).")

    is_installment = models.BooleanField(default=False,
                                         help_text="Check if this payment is part of an installment plan.")
                                         
    installment_number = models.PositiveIntegerField(blank=True, null=True,
                                                     help_text="The current installment number.")
                                                     
    total_installments = models.PositiveIntegerField(blank=True, null=True,
                                                     help_text="The total number of installments.")

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                          help_text="Fixed discount amount applied to the payment.")
                                          
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'),
                                              help_text="Percentage discount applied to the payment.")

    balance_before_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                 help_text="Balance remaining before this payment.")
                                                 
    balance_after_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                 help_text="Balance remaining after this payment.")
    
    date_recorded = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time the payment was recorded."
    )

    confirm_payment = models.BooleanField(default=False, verbose_name='confirm the payment')

    class Meta:
        ordering = ['-payment_date']
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment of {self.amount_received} for {self.student.first_name} {self.student.last_name} ({self.payment_category}) for {self.term} - {self.session}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
        
        if not is_new:
            old_payment = Payment.objects.get(pk=self.pk)
            old_status = old_payment.status
            # Retrieve previous balance for calculation
            prev_balance_ledger = StudentAccountLedger.objects.filter(
                student=self.student,
                session=self.session,
                term=self.term
            ).first()
            if prev_balance_ledger:
                self.balance_before_payment = prev_balance_ledger.balance

        super().save(*args, **kwargs)

        # Update the ledger and create a receipt only if the payment is 'completed' and was not before
        if self.status == 'completed' and (is_new or old_status != 'completed'):
            # Step 1: Update the ledger
            update_student_ledger(self.student, self.session, self.term)

            # Step 2: Get the updated ledger entry to calculate balance_after_payment
            try:
                ledger_entry = StudentAccountLedger.objects.get(
                    student=self.student,
                    session=self.session,
                    term=self.term
                )
                self.balance_after_payment = ledger_entry.balance
            except StudentAccountLedger.DoesNotExist:
                self.balance_after_payment = Decimal('0.00')

            # Step 3: Save again to update the balance_after_payment field on the Payment instance
            super().save(update_fields=['balance_after_payment'])

            # Step 4: Create or get the receipt instance for this payment
            receipt, created = Receipt.objects.get_or_create(
                payment=self,
                defaults={
                    'generated_by': self.recorded_by,
                }
            )
            # If the receipt already existed and the payment details changed, update it
            if not created:
                receipt.generated_by = self.recorded_by
                receipt.save()

    def delete(self, *args, **kwargs):
        student = self.student
        term = self.term
        session = self.session
        super().delete(*args, **kwargs)
        # Update the ledger after a payment is deleted
        update_student_ledger(student, session, term)


# Receipt Model
class Receipt(models.Model):
    """
    Represents a payment receipt generated after a successful payment.
    """
    payment = models.OneToOneField('Payment', on_delete=models.CASCADE, related_name='receipt',
                                   help_text="The payment associated with this receipt.")
    receipt_number = models.CharField(max_length=50, unique=True,
                                      help_text="A unique identifier for the receipt.")
    issue_date = models.DateTimeField(auto_now_add=True,
                                      help_text="The date and time the receipt was issued.")
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text="The staff member who generated this receipt.")

    class Meta:
        ordering = ['-issue_date']
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"

    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)

        if is_new and not self.receipt_number:
            if not self.issue_date:
                self.issue_date = timezone.now()

            today_str = self.issue_date.strftime('%Y%m%d')
            last_receipt = Receipt.objects.filter(receipt_number__startswith=f"REC-{today_str}-").order_by('receipt_number').last()
            
            if last_receipt:
                try:
                    last_id_part = int(last_receipt.receipt_number.split('-')[-1])
                    new_id_part = last_id_part + 1
                except (ValueError, IndexError):
                    new_id_part = 1
            else:
                new_id_part = 1
                
            self.receipt_number = f"REC-{today_str}-{new_id_part:04d}"
            super().save(update_fields=['receipt_number'])

    def __str__(self):
        return f"Receipt #{self.receipt_number} for {self.payment.student}"
    

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


# Students Fee Assignment
# Student Fee Assignment
class StudentFeeAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_assignments')
    payment_category = models.ForeignKey(PaymentCategory, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = "Student Fee Assignment"
        verbose_name_plural = "Student Fee Assignments"
        unique_together = ('student', 'payment_category', 'term', 'session')

    def __str__(self):
        return f"{self.student} - {self.payment_category} ({self.term} {self.session})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        update_student_ledger(self.student, self.session, self.term)
        
    def delete(self, *args, **kwargs):
        student = self.student
        term = self.term
        session = self.session
        super().delete(*args, **kwargs)
        update_student_ledger(student, session, term)


# CLASS TEMPLATE MODEL
class ClassFeeTemplate(models.Model):
    student_class = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='fee_templates')
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    payment_category = models.ForeignKey(PaymentCategory, on_delete=models.CASCADE)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Class Fee Template"
        verbose_name_plural = "Class Fee Templates"
        unique_together = ('student_class', 'term', 'session', 'payment_category')

    def __str__(self):
        return f"{self.student_class.name} - {self.payment_category.name} ({self.term.name}, {self.session.name})"
    

# PAYMENT NOTIFICATION
class PaymentNotification(models.Model):
    """
    Records a notification from a student/parent that a payment has been made offline.
    This record is processed manually by an administrator.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('PROCESSED', 'Processed (Payment Recorded)'),
        ('REJECTED', 'Rejected (Invalid Proof)'),
    ]

    # --- NEW: Define Choices for Payment Method ---
    METHOD_CHOICES = [
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('CASH_DEPOSIT', 'Cash Deposit (Bank)'),
        ('POS', 'POS Transaction'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other Offline Method'),
    ]
    # ----------------------------------------------
    #School Bank Account they paid to
    bank_account = models.ForeignKey(
        'payments.BankDetail',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="School Bank Account",
        help_text="The specific school bank account the payment was made to."
    )
    # Who is making the payment/for whom
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, verbose_name="Student Paid For")
    
    # Details of the payment
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    
    # --- FIX: Replaced ForeignKey with CharField using METHOD_CHOICES ---
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='BANK_TRANSFER')
    # -------------------------------------------------------------------
    
    transaction_id = models.CharField(max_length=100, blank=True, null=True, 
                                     help_text="Bank/Gateway Transaction Reference (if any).")
    payment_date = models.DateField(default=timezone.now)

    # Contextual information
    session = models.ForeignKey('curriculum.Session', on_delete=models.PROTECT, null=True, blank=True)
    term = models.ForeignKey('curriculum.Term', on_delete=models.PROTECT, null=True, blank=True)
    
    # Status and Audit
    notified_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, 
                                     help_text="User who submitted the form.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    submission_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Any additional notes from the payer.")
    
    # --- Optional: Field for Proof of Payment Upload ---
    # proof_of_payment = models.FileField(upload_to='payment_proofs/', blank=True, null=True)

    class Meta:
        verbose_name = "Payment Notification"
        verbose_name_plural = "Payment Notifications"
        ordering = ['-submission_date']

    def __str__(self):
        return f"Notification for {self.student} - {self.amount_paid} - {self.status}"