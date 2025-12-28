from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.auth.models import User
from django.utils import timezone # For the new sent_at field
from pages.models import Newsletter
from curriculum.models import SchoolIdentity
import time

class Command(BaseCommand):
    help = 'Sends unsent newsletters to the target audience in batches'

    def handle(self, *args, **kwargs):
        # 1. Fetch the first unsent newsletter
        newsletter = Newsletter.objects.filter(sent=False).first()
        if not newsletter:
            self.stdout.write("No pending newsletters.")
            return

        school_info = SchoolIdentity.objects.first()
        
        # 2. Determine audience
        all_active_users = User.objects.filter(is_active=True).exclude(email="")
        
        if newsletter.target_audience == 'TEST':
            # Sends only to the person who created the newsletter (or the Superuser)
            users = all_active_users.filter(is_superuser=True)[:1] 
        elif newsletter.target_audience == 'PARENTS':
            users = all_active_users.filter(parent__isnull=False)
        elif newsletter.target_audience == 'STUDENTS':
            users = all_active_users.filter(student__isnull=False)
        elif newsletter.target_audience == 'STAFF':
            users = all_active_users.filter(teacher__isnull=False)
        elif newsletter.target_audience == 'ADMINS':
            users = all_active_users.filter(is_staff=True)
        else: # Default for 'ALL'
            users = all_active_users

        recipient_count = users.count()
        self.stdout.write(f"Sending '{newsletter.subject}' to {recipient_count} recipients...")

        # 3. Prepare Content
        html_content = render_to_string('emails/newsletter_template.html', {
            'message': newsletter.message,
            'subject': newsletter.subject,
            'school_info': school_info
        })
        text_content = strip_tags(newsletter.message)

        # 4. Batch sending
        success_count = 0
        for user in users:
            try:
                msg = EmailMultiAlternatives(
                    newsletter.subject,
                    text_content,
                    None, # Uses DEFAULT_FROM_EMAIL from settings.py
                    [user.email]
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send()
                
                success_count += 1
                # Gmail is strict; 1 second delay is safer for larger lists
                time.sleep(1) 
            except Exception as e:
                self.stderr.write(f"Failed to send to {user.email}: {e}")

        # 5. Mark as Sent with Timestamp for the Admin Status Column
        newsletter.sent = True
        newsletter.sent_at = timezone.now() # This updates the Admin status badge
        newsletter.save()

        self.stdout.write(f"Done! Successfully sent {success_count} of {recipient_count} emails.")