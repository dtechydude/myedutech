from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile
from students.models import Student
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
        fields = [ 'state_of_origin', 'bio', 'phone' ]
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



# Student Enrollment Form
class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repeat Password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']

    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password'] != cd['password2']:
            raise forms.ValidationError('Passwords don\'t match.')
        return cd['password2']



class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'USN', 'middle_name', 'current_class', 'class_group', 
            'gender', 'DOB', 'blood_group', 'genotype', 
            'health_remark', 'student_type', 'hostel_name',
            'date_admitted', 'class_on_admission', 
            'guardian_name', 'guardian_address', 'guardian_phone', 
            'guardian_email', 'relationship', 
        ]
        widgets = {
            'USN': forms.TextInput(attrs={'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super(StudentEnrollmentForm, self).__init__(*args, **kwargs)

        # Add custom IDs to date fields for Tempus Dominus
        self.fields['DOB'].widget.attrs.update({'id': 'id_DOB'})
        self.fields['date_admitted'].widget.attrs.update({'id': 'id_date_admitted'})

        # Add Bootstrap classes for styling
        for visible in self.visible_fields():
            if not isinstance(visible.field.widget, forms.HiddenInput):
                visible.field.widget.attrs['class'] = 'form-control'
 
    # Guardian details are part of the Student model, so we don't need separate fields here.
    # The form automatically handles the fields defined in `Meta`.