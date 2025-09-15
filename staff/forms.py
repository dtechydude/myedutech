from tkinter import Widget
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Teacher
from curriculum.models import Subject, Standard
# your_app_name/forms.py



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




# Signup Form For Teachers 
class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email')
    
    # Custom validation to check if username is available
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if get_user_model().objects.filter(username=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
        return username

class TeacherForm(forms.ModelForm):
    # Add first_name and last_name fields to the form
    first_name = forms.CharField(max_length=150, required=True, label='First Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter First Name'}))
    last_name = forms.CharField(max_length=150, required=True, label='Last Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter Last Name'}))
    middle_name = forms.CharField(max_length=150, required=False, label='Middle Name',
        widget=forms.TextInput(attrs={'placeholder': 'Enter Middle Name'}))

    standards_assigned = forms.ModelMultipleChoiceField(
        queryset=Standard.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    subjects_taught = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    
    class Meta:
        model = Teacher
        fields = [
            'first_name', 'middle_name', 'last_name', 'gender', 'marital_status', 
            'phone_home', 'DOB', 'date_employed', 'staff_role', 'dept', 
            'standards_assigned', 'subjects_taught', 'qualification', 'year', 
            'institution', 'professional_body', 'guarantor_name', 'guarantor_phone', 
            'guarantor_address', 'guarantor_email', 'next_of_kin_name', 
            'next_of_kin_address', 'next_of_kin_phone',
        ]
        
        widgets = {
            'DOB': forms.DateInput(attrs={'type': 'date'}),
            'date_employed': forms.DateInput(attrs={'type': 'date'}),
            'guarantor_address': forms.Textarea(attrs={'rows': 2}),
            'next_of_kin_address': forms.Textarea(attrs={'rows': 2}),
        }