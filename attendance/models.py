from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from students.models import Student
from datetime import date
from django.utils import timezone
from curriculum.models import Session, Term



class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    present = models.BooleanField(default=False)
    # Add other attendance-specific fields if needed (e.g., status: 'P', 'A', 'L')

    class Meta:
        # Ensures that a student can only have one attendance record per day
        unique_together = ('student', 'date')
        ordering = ['-date', 'student__first_name'] # Order by date (desc) and student name

    def __str__(self):
        return f"{self.student.first_name} - {self.date} - {'Present' if self.present else 'Absent'}"





# Attendance Configuration
class AttendanceConfiguration(models.Model):
    """
    Stores attendance settings for a session/term.
    Applies to all students.
    """

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE
    )

    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE
    )

    total_school_days = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = (
            'session',
            'term'
        )

    def __str__(self):
        return (
            f"{self.session} - "
            f"{self.term} "
            f"({self.total_school_days} Days)"
        )

# Manual Attendance taking
class AttendanceSummary(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_summaries'
    )

    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    days_present = models.PositiveIntegerField(default=0)

    remarks = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'session', 'term')

    @property
    def total_school_days(self):
        config = AttendanceConfiguration.objects.filter(
            session=self.session, term=self.term
        ).first()
        return config.total_school_days if config else 0

    @property
    def days_absent(self):
        # Always derived from days_present + the configured total —
        # can never go stale or be set incorrectly by anything else.
        return max(self.total_school_days - self.days_present, 0)

    @property
    def attendance_percentage(self):
        if self.total_school_days > 0:
            return round((self.days_present / self.total_school_days) * 100, 2)
        return 0

    def __str__(self):
        return f"{self.student} - {self.term}"