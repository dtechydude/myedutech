from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    A simple in-app notification. One row per recipient.
    Shared by the lesson, assignment and lesson-note features; create them
    ONLY through `elearning.notices.services.notify()`.
    """

    class Category(models.TextChoices):
        LESSON = 'lesson', 'New lesson'
        ASSIGNMENT = 'assignment', 'Assignment'
        GRADE = 'grade', 'Graded work'
        LESSON_NOTE = 'lesson_note', 'Lesson note'
        GENERAL = 'general', 'General'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='elearning_notifications')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=300, blank=True,
                           help_text='Internal link only (must start with /).')
    # Lets a job (e.g. due-date reminders) avoid notifying the same person twice.
    dedupe_key = models.CharField(max_length=100, blank=True, db_index=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'elearning'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['recipient', 'is_read', '-created_at'])]

    def __str__(self):
        return f'{self.title} → {self.recipient}'

    @property
    def icon(self):
        return {
            self.Category.LESSON: 'fa-book-open',
            self.Category.ASSIGNMENT: 'fa-tasks',
            self.Category.GRADE: 'fa-star',
            self.Category.LESSON_NOTE: 'fa-clipboard-check',
        }.get(self.category, 'fa-bell')

    @property
    def color(self):
        return {
            self.Category.LESSON: 'primary',
            self.Category.ASSIGNMENT: 'warning',
            self.Category.GRADE: 'success',
            self.Category.LESSON_NOTE: 'info',
        }.get(self.category, 'secondary')

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


# Connect the automatic triggers (new lesson / new assignment / graded work).
from . import signals  # noqa: E402,F401