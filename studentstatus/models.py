from django.conf import settings
from django.db import models

from .constants import STATUS_CHOICES


class StudentStatusLog(models.Model):
    """
    Immutable audit trail of every front-end status change.

    Student / admin names are snapshotted so the record still reads correctly
    if the student or the admin account is later deleted.
    """
    student = models.ForeignKey(
        'students.Student', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='status_logs',
    )
    student_name = models.CharField(max_length=120)
    student_usn = models.CharField(max_length=100, blank=True)

    old_status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    new_status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    reason = models.TextField(blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='student_status_changes',
    )
    changed_by_name = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-changed_at', '-pk']
        verbose_name = 'Student Status Log'
        verbose_name_plural = 'Student Status Logs'
        indexes = [models.Index(fields=['student', '-changed_at'])]

    def __str__(self):
        return f"{self.student_name}: {self.old_status} → {self.new_status}"