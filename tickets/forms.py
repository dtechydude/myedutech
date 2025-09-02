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