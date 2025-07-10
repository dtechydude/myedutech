from tkinter import Widget
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Teacher



# teacher
class TeacherRegisterForm(forms.ModelForm):

    class Meta:
        model = Teacher
        fields = '__all__'
        

class TeacherUpdateForm(forms.ModelForm):

    class Meta:
        model = Teacher
        fields = '__all__'
        # exclude = ('user',)


#staff
class StaffRegisterForm(forms.ModelForm):
    pass

    # class Meta:
    #     model = Staff
    #     fields = '__all__'
        

class StaffUpdateForm(forms.ModelForm):
    pass

    # class Meta:
    #     model = Staff
    #     fields = '__all__'
    #     # exclude = ('user',)