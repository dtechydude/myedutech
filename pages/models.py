from django.db import models


class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')

    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        # unique_together = ['acc_number', 'bank_name']