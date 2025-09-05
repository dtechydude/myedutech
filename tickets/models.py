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
    # Add choices for the audience field
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('teachers', 'Teachers'),
        ('students', 'Students'),
    ]

    is_broadcast = models.BooleanField(default=False)
    audience = models.CharField(
        max_length=20, 
        choices=AUDIENCE_CHOICES, 
        default='all', 
        blank=True
    )
    
    # This assumes the 'author' is a ForeignKey to the User model.
    # If a ticket is a broadcast, the author will be an admin.
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets_submitted')
    
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
    

class TicketReadStatus(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Ticket Read Statuses'
        unique_together = ('user', 'ticket') # Ensures one entry per user-ticket pair

    def __str__(self):
        return f"{self.user.username} read {self.ticket.title}"