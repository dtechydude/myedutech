from django.db import models
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field

class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')

    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        # unique_together = ['acc_number', 'bank_name']



class Newsletter(models.Model):
    AUDIENCE_CHOICES = [
        ('TEST', 'Only Me (Testing)'),
        ('ALL', 'All Users'),
        ('PARENTS', 'Parents Only'),
        ('STUDENTS', 'Students Only'),
        ('STAFF', 'Teachers/Staff Only'),
        ('ADMINS', 'Admins Only'),
    ]

    subject = models.CharField(max_length=255)
    # The 'Friendly UI' editor replaces the old TextField
    message = CKEditor5Field('Message', config_name='extends')
    target_audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    # Field to track the automation time
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} ({self.target_audience})"