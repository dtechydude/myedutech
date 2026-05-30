"""
KwikSchools — Prep Report Card Signals
========================================
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PrepReportCard


@receiver(post_save, sender=PrepReportCard)
def log_status_change(sender, instance, created, **kwargs):
    """
    Audit log entry when a report card status changes.
    Requires the project's AuditLog model (adjust import to match your setup).
    """
    try:
        from audit_logs.models import AuditLog  # adjust to your audit app
        action = "PREP_REPORT_CREATED" if created else "PREP_REPORT_UPDATED"
        AuditLog.objects.create(
            action=action,
            target_model="PrepReportCard",
            target_id=instance.pk,
            description=(
                f"Report card for {instance.student} — "
                f"{instance.period} | Status: {instance.status}"
            ),
        )
    except Exception:
        pass  # Audit logging is non-critical; never break the main flow
