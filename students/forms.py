from tkinter import Widget
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Student





class StudentRegisterForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        
        # widgets = {
        #     'date_employed': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),

        #     'year': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),

        #  }

       # Widget = {'date_employed': forms.DateInput()}

class StudentUpdateForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        exclude = ('user', 'USN', 'student_status', 'badge', 'form_teacher', 'date_admitted', 'last_name', 'first_name',  'standard', 'class_on_admission')




