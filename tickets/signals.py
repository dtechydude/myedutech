# tickets/signals.py (add to existing file)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from .models import Ticket, Comment
from django.conf import settings

# ... (notify_admin_on_new_ticket function) ...

@receiver(post_save, sender=Comment)
def notify_author_on_response(sender, instance, created, **kwargs):
    if created:
        ticket = instance.ticket
        author_email = ticket.author.email
        
        # Check if the comment is from an admin
        # You can use instance.author.is_staff or instance.is_admin_response
        if instance.author != ticket.author:
            subject = f"Update on your ticket: {ticket.title}"
            message = (
                f"A new response has been added to your ticket titled '{ticket.title}'.\n\n"
                f"Response: {instance.text}\n"
                f"Link: http://your-school-app.com/tickets/{ticket.pk}/" # Change this to your actual student/teacher URL
            )
            # send_mail(
            #     subject,
            #     message,
            #     settings.DEFAULT_FROM_EMAIL,
            #     [author_email],
            #     fail_silently=False,
            # )