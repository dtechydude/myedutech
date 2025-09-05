# tickets/forms.py

from django import forms
from .models import Ticket, Comment

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'priority']

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']

# Admin only broadcast form
class BroadcastTicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'audience']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = "Broadcast Subject"
        self.fields['description'].label = "Message Content"
