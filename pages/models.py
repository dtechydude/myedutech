from django.db import models
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field


class BankDetail(models.Model):
    acc_name = models.CharField(max_length=50, blank=False)
    acc_number = models.CharField(max_length=10, blank=False)
    bank_name = models.CharField(max_length=50, blank=False, verbose_name='Bank Name')
    description = models.CharField(max_length=50, blank=False, verbose_name='Description')


    def __str__(self):
        return f'{self.acc_number} - {self.bank_name}'

    class Meta:
        ordering:['bank_name']
        unique_together = ['acc_number', 'bank_name']


class Newsletter(models.Model):
    AUDIENCE_CHOICES = [
        ('TEST', 'Only Me (Testing)'),
        ('ALL', 'All Users'),
        ('PARENTS', 'Parents Only'),
        ('STUDENTS', 'Students Only'),
        ('STAFF', 'Teachers/Staff Only'),
        ('ADMINS', 'Admins Only'),
    ]

    subject = models.CharField(max_length=255)
    # The 'Friendly UI' editor replaces the old TextField
    message = CKEditor5Field('Message', config_name='extends')
    target_audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    # Field to track the automation time
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} ({self.target_audience})"




# ============================================================================
# HYBRID INTEGRATION HUB — Models, View, and URLs
# ============================================================================
# A central page linking teachers, students, and school admins (superuser/
# staff) out to: lesson notes, live classes, downloadable materials,
# Google for Education, Microsoft Teams for Education, and Bulk SMS —
# segregated by role.
#
# Design choices:
#  - HybridIntegrationSettings is a SINGLETON row (same pattern as your
#    existing SchoolIdentity model) so each personalized school deployment
#    can plug in its own Google Workspace / Microsoft 365 / Bulk SMS
#    provider links without a code change — fits the one-time-payment,
#    personalized-deployment model.
#  - Internal links (lesson notes, live classes, materials, communication
#    center, e-learning dashboard) are resolved with a `_safe_reverse()`
#    helper so the hub degrades gracefully (shows a disabled "Coming
#    soon" tile) instead of throwing a 500 if a URL name doesn't match
#    your existing app — see "⚠️ VERIFY" comments below.
#  - Suggested placement: put the model in your `core` app (wherever
#    SchoolIdentity already lives), the view/urls in `core` as well, or a
#    new lightweight `integrations` app if you prefer to keep it separate.
#
# ⚠️ THINGS TO VERIFY / ADJUST BEFORE RUNNING:
#   1. The `elearning:*` and `communication:*` URL names below are
#      assumptions based on your module list (E-Learning, Newsletter &
#      Bulk Communication). Swap in your real url names.
#   2. `hasattr(request.user, 'teacher')` / `'student'` mirrors the
#      pattern already used elsewhere in your codebase (e.g. the report
#      card views), so this should already match your user model setup.
# ============================================================================


# ----------------------------------------------------------------------------
# 1) models.py
# ----------------------------------------------------------------------------
from django.conf import settings
from django.db import models


class HybridIntegrationSettings(models.Model):
    """
    Singleton settings row storing this school's external EdTech
    integration links. Lets the school admin plug in their own sign-in /
    dashboard links per deployment instead of hardcoding them.
    """

    # ---- Google for Education ----
    google_classroom_url = models.URLField(
        blank=True, default="https://classroom.google.com/",
        help_text="Sign-in link for your school's Google Classroom / Workspace for Education domain."
    )
    google_meet_url = models.URLField(
        blank=True, default="https://meet.google.com/",
        help_text="Default Google Meet link/landing page for live classes."
    )
    google_workspace_admin_url = models.URLField(
        blank=True, help_text="Google Admin Console link — shown to school admins only."
    )

    # ---- Microsoft Teams for Education ----
    microsoft_teams_url = models.URLField(
        blank=True, default="https://teams.microsoft.com/",
        help_text="Sign-in link for Microsoft Teams for Education."
    )
    microsoft_365_admin_url = models.URLField(
        blank=True, help_text="Microsoft 365 Admin Center link — shown to school admins only."
    )

    # ---- Bulk SMS ----
    bulk_sms_enabled = models.BooleanField(
        default=False,
        help_text="Turn on to expose the Bulk SMS tile to school admins/teachers."
    )
    bulk_sms_provider_name = models.CharField(
        max_length=100, blank=True,
        help_text="e.g. Termii, KudiSMS, Africa's Talking, Twilio."
    )
    bulk_sms_provider_url = models.URLField(
        blank=True, help_text="Link to your Bulk SMS provider's dashboard/portal (if external)."
    )

    # ---- Optional secondary live-class provider ----
    zoom_url = models.URLField(
        blank=True, help_text="Optional Zoom link, if used instead of/alongside Google Meet."
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_integration_settings'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hybrid Integration Settings"
        verbose_name_plural = "Hybrid Integration Settings"

    def __str__(self):
        return "Hybrid Integration Settings"

    @classmethod
    def get_solo(cls):
        """Always returns the single settings row, creating it on first use."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton — there is only ever one settings row
        super().save(*args, **kwargs)

