from django.contrib import admin, messages
from django.utils.html import format_html
from django.core.management import call_command
from .models import Newsletter

@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    # 1. Update list_display to include our custom status_tag
    list_display = ('subject', 'target_audience', 'status_tag', 'created_at')
    
    # 2. Add filters so you can quickly see 'Sent' vs 'Pending'
    list_filter = ('sent', 'target_audience')
    
    # 3. Make these readonly so the "Robot" handles them, not human clicks
    readonly_fields = ('sent', 'sent_at') 
    
    # 4. Your merged Action
    actions = ['send_newsletter_action']

    @admin.display(description="Delivery Status")
    def status_tag(self, obj):
        """Creates a pretty badge in the list view"""
        if obj.sent:
            return format_html(
                '<b style="color: #28a745;">✔ Sent</b> <br>'
                '<small style="color: #666;">{}</small>',
                obj.sent_at.strftime("%d %b, %H:%M") if obj.sent_at else ""
            )
        return format_html('<b style="color: #fd7e14;">⏳ Pending</b>')

    def send_newsletter_action(self, request, queryset):
        """Merged action to trigger the management command manually"""
        unsent_count = queryset.filter(sent=False).count()
        
        if unsent_count > 0:
            try:
                # This replaces the 'undefined' task and calls your script
                call_command('send_pending_newsletters')
                self.message_user(request, f"Successfully triggered sending for {unsent_count} newsletter(s).")
            except Exception as e:
                self.message_user(request, f"Error: {e}", level='error')
        else:
            self.message_user(request, "Selected newsletters were already sent.", level='warning')

    send_newsletter_action.short_description = "Send selected newsletters immediately"