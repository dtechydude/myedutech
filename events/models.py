from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse # ADD THIS LINE

class Event(models.Model):
    VISIBILITY_CHOICES = (
        ('student', 'Students Only'),
        ('teacher', 'Teachers Only'),
        ('admin', 'Admin Only'),
        ('all', 'All Users'),
    )

    title = models.CharField(max_length=200, help_text="Title of the event")
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField(help_text="Start time of the event")
    end_time = models.DateTimeField(help_text="End time of the event")
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='all')

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"
        ordering = ['start_time']

    def __str__(self):
        return self.title

    @property
    def get_html_url(self):
        """Returns a URL to the event's detail page."""
        url = reverse('events:event_edit', args=(self.id,))
        return f'<a href="{url}"> {self.title} </a>'