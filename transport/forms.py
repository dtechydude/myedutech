# transport/forms.py
from django import forms
from .models import StudentOnRoute , BusPayment
from students.models import Student
from curriculum.models import Session, Term


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



#===========================================================================

class BusEnrollmentForm(forms.ModelForm):
    # Searchable field for Admin
    student_search = forms.CharField(
        label="Search Student",
        required=False,
        widget=forms.TextInput(attrs={
            'list': 'student-list', 
            'placeholder': 'Type Name or ID...',
            'class': 'form-control'
        })
    )

    class Meta:
        model = StudentOnRoute
        fields = ['student', 'route', 'term', 'session']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # 1. Fetch Current Academic Data
        current_session = Session.objects.filter(is_current=True).first()
        current_term = Term.objects.filter(is_current=True).first()

        # 2. Styling and Pre-fills
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
            if field_name == 'session' and current_session:
                self.initial['session'] = current_session
            if field_name == 'term' and current_term:
                self.initial['term'] = current_term

        # 3. User-Specific Logic
        if self.request:
            user = self.request.user
            is_admin = user.is_staff or user.is_superuser

            if not is_admin:
                # Student View: Hide search, lock ID, lock Term/Session
                self.fields['student_search'].widget = forms.HiddenInput()
                current_student = Student.objects.filter(user=user).first()
                if current_student:
                    self.fields['student'].queryset = Student.objects.filter(pk=current_student.pk)
                    self.initial['student'] = current_student
                    self.fields['student'].widget = forms.HiddenInput()
                
                if current_session:
                    self.fields['session'].queryset = Session.objects.filter(pk=current_session.pk)
                    self.fields['session'].disabled = True
                if current_term:
                    self.fields['term'].queryset = Term.objects.filter(pk=current_term.pk)
                    self.fields['term'].disabled = True
            else:
                # Admin View: Hide the actual student ID field (handled by search)
                self.fields['student'].widget = forms.HiddenInput()
                self.all_students = Student.objects.all().order_by('last_name')

    def clean(self):
        cleaned_data = super().clean()
        
        # Recovery for disabled fields for students
        if self.request and not (self.request.user.is_staff or self.request.user.is_superuser):
            for field in ['student', 'term', 'session']:
                if field not in cleaned_data:
                    cleaned_data[field] = self.initial.get(field)

        student = cleaned_data.get('student')
        route = cleaned_data.get('route')
        term = cleaned_data.get('term')
        session = cleaned_data.get('session')

        # Duplicate Check
        if all([student, route, term, session]):
            exists = StudentOnRoute.objects.filter(
                student=student, route=route, term=term, session=session
            ).exclude(pk=self.instance.pk if self.instance else None).exists()

            if exists:
                raise forms.ValidationError(f"{student.get_full_name()} is already enrolled for this route/term.")
        
        return cleaned_data

#==================================================================================


class BusPaymentForm(forms.ModelForm):
    class Meta:
        model = BusPayment
        # Remove 'enrollment' from the fields list so it doesn't show up in the box
        fields = ('amount_paid', 'payment_date', 'payment_method', 'short_note') 
        labels = {
            'short_note': 'Payment Notes',
        }
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }