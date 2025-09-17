from django.forms import ModelForm, DateTimeInput
from .models import Event

class EventForm(ModelForm):
  class Meta:
    model = Event
    fields = ['title', 'description', 'start_time', 'end_time', 'visibility']
    widgets = {
      'start_time': DateTimeInput(attrs={'type': 'datetime-local'}),
      'end_time': DateTimeInput(attrs={'type': 'datetime-local'}),
    }