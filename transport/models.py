from django.db import models
from staff.models import Teacher
from django.contrib.auth.models import User
from students.models import Student
from django.template.defaultfilters import slugify
from django.conf import settings
from django.urls import reverse
from django.core.validators import MinLengthValidator, MaxValueValidator, MinValueValidator 
from curriculum.models import Session, Term


# Create your models here.


class Route(models.Model):
    route_id = models.CharField(max_length=8,null=True, unique=True,  blank=True, help_text='Could be Bus Number')
    name = models.CharField(max_length=200, blank=True, unique=True )
    direction = models.CharField(max_length=200, blank=True)
    bus_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0.0, null=True, help_text='Bus Fare')
    staff_in_charge = models.ForeignKey(Teacher, on_delete=models.CASCADE, default=None, null=True, related_name='official_staff')
    driver = models.CharField(max_length=200, blank=True, unique=True, verbose_name='Driver Name')
    driver_phone = models.CharField(max_length=11, blank=True)
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        ordering = ['route_id']
        verbose_name = 'Bus Routes & Fares'
        verbose_name_plural = 'Bus Routes & Fares'

    def __str__ (self):
        return f'{self.name} - {self.route_id}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# class StudentOnRoute(models.Model):
#     student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='studentonroute',
#                                 help_text="The student associated with this route.")
#     route = models.ForeignKey(Route, on_delete=models.CASCADE, default= None, related_name='routes')
#     session = models.ForeignKey(Session, on_delete=models.CASCADE, default=None, null=True, related_name='official_staff')
#     term = models.ForeignKey(Term, on_delete=models.CASCADE, default=None, null=True, related_name='official_staff')
#     amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.0, null=True, help_text='Amount Paid For Bus')
#     PAYMENT_METHOD_CHOICES = [
#         ('cash', 'Cash'),
#         ('bank_transfer', 'Bank Transfer'),
#         ('card', 'Card Payment'),
#         ('online_gateway', 'Online Gateway'),
#     ]  
#     payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True,
#                                       help_text="The method used for the payment.")
#     payment_date = models.DateField(verbose_name='Payment Date', blank=True, null=True)
         
#     signup_date = models.DateTimeField(auto_now_add=True)
#     is_approved = models.BooleanField(default=False,  help_text="Check if payment is confirmed.")
#     is_active_on_bus = models.BooleanField(default=False, help_text="Check if student is ACTIVE on bus Uncheck If Student in INACTIVE")
#     updated = models.DateTimeField(auto_now=True)

#     class Meta:
#         unique_together = (('student', 'route'),)
#         verbose_name = "Student on Route"
#         verbose_name_plural = "Students on Routes"

#     def __str__(self):
#         # If student is a User, then access username directly
#         return f"{self.student.username} - {self.route.name}" 
   

#     class Meta:
#         ordering = ['student' ]
#         unique_together = ['student', 'route']
#         verbose_name = 'Students On Bus Route'
#         verbose_name_plural = 'Students On Bus Route'
    

#     def __str__ (self):
#        return f'{self.student}'
    
    
#     @property
#     def balance_payment (self):
#        return self.route.bus_fee - (self.amount_paid)
    


class StudentOnRoute(models.Model):
    """
    Manages a student's enrollment on a bus route for a specific term and session.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='bus_enrollments')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='student_enrollments')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='bus_enrollments')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='bus_enrollments')
    is_active = models.BooleanField(default=True, help_text="Is the student currently active on this route?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'route', 'session', 'term')
        verbose_name = 'Student Bus Enrollment'
        verbose_name_plural = 'Students Bus Enrollments'

    def __str__(self):
        return f'{self.student.last_name} on {self.route.name} ({self.term.name} {self.session.name})'


class BusPayment(models.Model):
    """
    Tracks individual payments made for bus enrollment.
    """
    enrollment = models.ForeignKey(StudentOnRoute, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, help_text='Amount paid for this transaction.')
    payment_date = models.DateField(verbose_name='Payment Date')  # The field is now editable
    is_approved = models.BooleanField(default=False, help_text="Check if this payment is confirmed.")
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Card Payment'),
        ('online_gateway', 'Online Gateway'),
    ]
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True,
                                      help_text="The method used for the payment.")
    
    short_note = models.CharField(max_length=255, blank=True, null=True, 
                                  help_text="Any additional notes about the payment or payee.")

    def __str__(self):
        return f'Payment of {self.amount_paid} for {self.enrollment}'

    @property
    def is_confirmed(self):
        # A simple check for a confirmed payment. You can add more complex logic.
        return self.is_approved

    
