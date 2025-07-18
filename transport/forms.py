# transport/forms.py
from django import forms
from .models import StudentOnRoute 

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

class BusSignupForm(forms.ModelForm):
    class Meta:
        model = StudentOnRoute
        fields = ['route'] # Assuming student is automatically linked to the logged-in user

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None) # Pass request to form if needed for student
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        route = cleaned_data.get('route')
        # Assuming student is retrieved from the request's user
        student = self.request.user if self.request and hasattr(self.request.user, 'student') else None

        if student and route:
            if StudentOnRoute.objects.filter(student=student, route=route).exists():
                raise forms.ValidationError("You are already signed up for this bus route.")
        return cleaned_data