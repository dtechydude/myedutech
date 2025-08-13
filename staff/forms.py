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
    # This form no longer needs first/last name as they are now in step 1.
    subjects_taught = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Subjects Taught'
    )
    standards_assigned = forms.ModelMultipleChoiceField(
        queryset=Standard.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Standards Assigned'
    )

    class Meta:
        model = Teacher
        exclude = ['user', 'updated', 'created', 'active', 'first_name', 'last_name', 'middle_name']
        widgets = {
            'DOB': forms.DateInput(attrs={'type': 'date'}),
            'date_employed': forms.DateInput(attrs={'type': 'date'}),
            'year': forms.DateInput(attrs={'type': 'date'}),
        }
