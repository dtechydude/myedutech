# tickets/models.py
from django.db import models
from django.contrib.auth.models import User

class Ticket(models.Model):
    STATUS_CHOICES = (
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
    )
    
    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    )
    
    CATEGORY_CHOICES = (
        ('Academic', 'Academic'),
        ('Technical Support', 'Technical Support'),
        ('Financial Aid', 'Financial Aid'),
        ('Facilities', 'Facilities'),
        ('General Inquiry', 'General Inquiry'),
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    # The 'author' field is the one causing the clash.
    # The default related_name is 'ticket_set', which might clash with another 'ticket' model.
    # A safe related_name is `tickets_submitted`.
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets_submitted')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_assigned')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='General Inquiry')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ticket #{self.id}: {self.title}"
    

class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    # The 'author' field is causing the clash with your curriculum app's comment model.
    # The default related_name is 'comment_set'.
    # We will use 'ticket_comments' to be safe.
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_comments')
    text = models.TextField()
    is_admin_response = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket}"