# transport/forms.py
from django import forms
from .models import StudentOnRoute , BusPayment
from students.models import Student

class StudentOnRouteForm(forms.ModelForm):
    class Meta:
        model = StudentOnRoute
        fields = ['student', 'route'] # Or specify the fields you want to display/edit
        # Example: fields = ['student', 'bus_route', 'pickup_time']


class StudentBusCreateForm(forms.ModelForm):
    class Meta:
        model = StudentOnRoute
        fields = ['route'] # Or specify the fields you want to display/edit
        # Example: fields = ['student', 'bus_route', 'pickup_time']

# class BusSignupForm(forms.ModelForm):
#     class Meta:
#         model = StudentOnRoute
#         fields = ['route', 'amount_paid', 'payment_method', 'payment_date'] # Assuming student is automatically linked to the logged-in user
#         widgets = {
#             'payment_date': forms.DateInput(
#                 format=('%d/%m/%Y'),
#                 attrs={'class': 'form-control', 
#                        'placeholder': 'Select a date',
#                        'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
#                       }),
#         }
#     def __init__(self, *args, **kwargs):
#         self.request = kwargs.pop('request', None) # Pass request to form if needed for student
#         super().__init__(*args, **kwargs)

#     def clean(self):
#         cleaned_data = super().clean()
#         route = cleaned_data.get('route')
#         # Assuming student is retrieved from the request's user
#         student = self.request.user if self.request and hasattr(self.request.user, 'student') else None

#         if student and route:
#             if StudentOnRoute.objects.filter(student=student, route=route).exists():
#                 raise forms.ValidationError("You are already signed up for this bus route.")
#         return cleaned_data


class BusEnrollmentForm(forms.ModelForm):
    """
    Form to handle a student's one-time enrollment on a bus route.
    """
    class Meta:
        model = StudentOnRoute
        fields = ['student', 'route', 'term', 'session']
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # If the user is a regular student, lock the student field to their own account.
        if self.request and not self.request.user.is_staff:
            try:
                # Retrieve the student object related to the logged-in user
                current_student = Student.objects.get(user=self.request.user)
                
                # Set the queryset for the 'student' field to only include the current student.
                # This ensures the form can only be submitted with this student.
                self.fields['student'].queryset = Student.objects.filter(pk=current_student.pk)
                
                # Pre-select the student and make the field read-only or hidden.
                self.initial['student'] = current_student
                self.fields['student'].disabled = True
            except Student.DoesNotExist:
                # Handle the case where the user is not a student
                pass

    def clean(self):
        cleaned_data = super().clean()
        
        # If the student field was disabled, retrieve its value from the initial data
        if self.request and not self.request.user.is_staff and 'student' not in cleaned_data:
            try:
                cleaned_data['student'] = Student.objects.get(user=self.request.user)
            except Student.DoesNotExist:
                raise forms.ValidationError("Student record not found.")

        student = cleaned_data.get('student')
        route = cleaned_data.get('route')
        term = cleaned_data.get('term')
        session = cleaned_data.get('session')
        
        # Validate that all required fields are present
        if not all([student, route, term, session]):
            raise forms.ValidationError("All fields are required for enrollment.")
        
        # Check for existing enrollment to prevent duplicates
        if StudentOnRoute.objects.filter(student=student, route=route, term=term, session=session).exists():
            raise forms.ValidationError("This student is already signed up for this bus route for the selected term and session.")
        
        return cleaned_data

class BusPaymentForm(forms.ModelForm):
    """
    Form to handle individual bus payments.
    """
    class Meta:
        model = BusPayment
        fields = ['amount_paid', 'payment_method']