from django import forms
# from transport.models import StudentBusPayment


# class BusPaymentForm(forms.ModelForm):
#      class Meta:
#         model = StudentBusPayment
#         fields = '__all__'
#         exclude = ('payee_id',)

#         widgets = {
#             'payment_date_a': forms.DateInput(
#                 format=('%d/%m/%Y'),
#                 attrs={'class': 'form-control', 
#                        'placeholder': 'Select a date',
#                        'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
#                       }),
#             'payment_date_b': forms.DateInput(
#                 format=('%d/%m/%Y'),
#                 attrs={'class': 'form-control', 
#                        'placeholder': 'Select a date',
#                        'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
#                       }),

#             'payment_date_c': forms.DateInput(
#                 format=('%d/%m/%Y'),
#                 attrs={'class': 'form-control', 
#                        'placeholder': 'Select a date',
#                        'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
#                       }),
#         }
#                         #Note that i removed user because it is an instance in the view already

class BusPaymentForm(forms.ModelForm):
     pass
    #  class Meta:
    #     model = StudentBusPayment
    #     fields = ['route', 'payment', 'amount_paid_a', 'bank_name_a', 'payment_date_a', 'remark_a']
    #     # exclude = ('payee_id',)

    #     widgets = {
    #         'payment_date_a': forms.DateInput(
    #             format=('%d/%m/%Y'),
    #             attrs={'class': 'form-control', 
    #                    'placeholder': 'Select a date',
    #                    'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
    #                   }),          

    #     }
    #                     #Note that i removed user because it is an instance in the view already
