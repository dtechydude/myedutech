from django.db import models
from staff.models import Teacher
from django.contrib.auth.models import User
from students.models import Student
from django.template.defaultfilters import slugify
from django.conf import settings
from django.urls import reverse
from django.core.validators import MinLengthValidator, MaxValueValidator, MinValueValidator 


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
        verbose_name = 'Route/Fare'

    def __str__ (self):
        return f'{self.name} - {self.route_id}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class StudentOnRoute(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='studentonroute',
                                help_text="The student associated with this route.")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, default= None, related_name='routes')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0.0, null=True, help_text='Amount Paid For Bus')
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Card Payment'),
        ('online_gateway', 'Online Gateway'),
    ]  
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True,
                                      help_text="The method used for the payment.")
    payment_date = models.DateField(verbose_name='Payment Date', blank=True, null=True)
         
    signup_date = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('student', 'route'),)
        verbose_name = "Student on Route"
        verbose_name_plural = "Students on Routes"

    def __str__(self):
        # If student is a User, then access username directly
        return f"{self.student.username} - {self.route.name}" 
   

    class Meta:
        ordering = ['student' ]

        unique_together = ['student', 'route']
    

    def __str__ (self):
       return f'{self.student}'
