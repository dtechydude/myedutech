from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse

from .links import parse_note_link, validate_google_note_link

session_validator = RegexValidator(r'^\d{4}/\d{4}$', 'Use the format 2026/2027.')


class LessonNote(models.Model):
    """
    A teacher's lesson note, kept in Google Drive. Only the LINK is stored
    here; the school reviews, comments on and edits the file in Google Drive,
    and records its decision (approve / request changes) in this app.
    """

    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Awaiting review'
        APPROVED = 'approved', 'Approved'
        REVISION = 'revision', 'Changes requested'

    class Term(models.TextChoices):
        FIRST = '1', 'First Term'
        SECOND = '2', 'Second Term'
        THIRD = '3', 'Third Term'

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='elearning_lesson_notes')
    standard = models.ForeignKey('curriculum.Standard', on_delete=models.PROTECT,
                                 related_name='+', verbose_name='Class')
    subject_name = models.CharField(max_length=100, verbose_name='Subject')
    academic_session = models.CharField(max_length=9, validators=[session_validator],
                                        help_text='e.g. 2026/2027')
    term = models.CharField(max_length=1, choices=Term.choices)
    week = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(20)])
    title = models.CharField(max_length=200, blank=True,
                             help_text='Optional — filled in automatically if left blank.')
    doc_link = models.URLField(
        max_length=500, validators=[validate_google_note_link],
        verbose_name='Google Drive link',
        help_text='Link to your lesson note in Google Docs, Sheets, Slides or Drive.',
    )
    teacher_note = models.TextField(max_length=500, blank=True,
                                    verbose_name='Message to the reviewer (optional)')

    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.SUBMITTED, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    related_name='elearning_lesson_notes_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remark = models.TextField(max_length=1000, blank=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'elearning'
        ordering = ['-submitted_at']
        verbose_name = 'Teacher lesson note'
        verbose_name_plural = 'Teacher lesson notes'
        constraints = [
            models.UniqueConstraint(
                fields=['teacher', 'standard', 'subject_name', 'academic_session', 'term', 'week'],
                name='elearning_lessonnote_unique_slot',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-submitted_at']),
            models.Index(fields=['teacher', 'status']),
        ]

    def __str__(self):
        return f'{self.title} — {self.teacher}'

    def save(self, *args, **kwargs):
        self.subject_name = ' '.join((self.subject_name or '').split())
        if not self.title:
            self.title = f'Week {self.week} – {self.subject_name} ({self.standard})'[:200]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('lessonnotes:detail', kwargs={'pk': self.pk})

    # ---- presentation helpers -------------------------------------------
    @property
    def teacher_display(self):
        return self.teacher.get_full_name() or self.teacher.get_username()

    @property
    def link_info(self):
        return parse_note_link(self.doc_link)

    @property
    def safe_link(self):
        """The link, only if it still passes validation (defence in depth for templates)."""
        info = self.link_info
        return info['url'] if info else ''

    @property
    def kind_label(self):
        info = self.link_info
        return info['label'] if info else 'Link'

    @property
    def kind_icon(self):
        info = self.link_info
        return info['icon'] if info else 'fa-file'

    @property
    def is_locked(self):
        return self.status == self.Status.APPROVED

    @property
    def badge_class(self):
        return {
            self.Status.APPROVED: 'success',
            self.Status.REVISION: 'warning text-dark',
        }.get(self.status, 'info text-dark')


class LessonNoteEvent(models.Model):
    """Audit trail: who did what to a lesson note, and when."""

    class Action(models.TextChoices):
        SUBMITTED = 'submitted', 'Submitted'
        EDITED = 'edited', 'Edited'
        RESUBMITTED = 'resubmitted', 'Resubmitted after changes'
        APPROVED = 'approved', 'Approved'
        REVISION = 'revision_requested', 'Changes requested'

    note = models.ForeignKey(LessonNote, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True, related_name='+')
    action = models.CharField(max_length=20, choices=Action.choices)
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'elearning'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.get_action_display()} — {self.note_id}'