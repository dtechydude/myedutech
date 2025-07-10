from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile
# from staff.models import Teacher


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField()
    last_name = forms.CharField()
   

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']



class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [ 'phone', 'user_type' ]



class UserUpdateForm(forms.ModelForm):
    # email = forms.EmailField(required=False)
    # first_name = forms.CharField()
    # last_name = forms.CharField()

    class Meta:
        model = User
        fields = [ 'email', 'last_name', 'first_name', ]


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [ 'state_of_origin', 'bio', 'phone', 'image' ]
        # widgets = {
        #     'date_of_birth': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),
        # }



class UserTwoUpdateForm(forms.ModelForm):
   
    class Meta:
        model = User
        fields = [ 'last_name', ]


class TeacherEmploymentUpdateForm(forms.ModelForm):
    pass 

    # class Meta:
    #     model = Teacher
    #     fields = ['first_name', 'qualification', 'year', 'marital_status', 'phone_home', 'professional_body', 'next_of_kin_name', 'next_of_kin_phone']