from django import forms
from .models import Quiz, Question
from results.models import Examination
from curriculum.models import Standard # Assuming this is where Standard lives

class TeacherQuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['examination', 'subject', 'term', 'number_of_questions', 'time']

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super(TeacherQuizForm, self).__init__(*args, **kwargs)
        
        if teacher:
            # 1. Get all Standards assigned to this teacher
            assigned_standards = teacher.standards_assigned.all()
            
            # 2. Filter Examinations that belong to those Standards
            # Note: Adjust 'standard' to whatever the field name is inside your Examination model
            self.fields['examination'].queryset = Examination.objects.filter(
                standard__in=assigned_standards
            ).distinct()

            # 3. Filter Subjects
            self.fields['subject'].queryset = teacher.subjects_taught.all()

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})




class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['content', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Enter question here...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']:
            self.fields[field].widget.attrs.update({'class': 'form-control'})