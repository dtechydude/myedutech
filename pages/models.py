from django.db import models
from django.contrib.auth.models import User


class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')

    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        # unique_together = ['acc_number', 'bank_name']


# class Parent(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE, help_text='The user account for this parent.')
#     guardian_name = models.CharField(max_length=60, blank=False)  
#     guardian_address = models.CharField(max_length=200, blank=True)  
#     guardian_phone = models.CharField(max_length=15, blank=True)
#     guardian_email = models.CharField(max_length=30, blank=True)
#     # You can add other parent-specific fields here if needed,
#     # e.g., address, phone_number, etc.
#     # The guardian_name, guardian_address, etc., from the Student model
#     # can be moved here to avoid redundancy.

#     def __str__(self):
#         return self.user.get_full_name()