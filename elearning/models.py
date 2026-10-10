from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
import os
from django.utils.html import strip_tags
from embed_video.fields import EmbedVideoField
from tinymce.models import HTMLField

from .services import extract_youtube_id, validate_web_link

# =====================================================================
# E-LEARNING APP — fully independent ('elearning' namespace).
# The only link to `curriculum` is the lazy 'curriculum.Standard' FK
# (single source of truth for the class list). Models that moved from
# curriculum keep their ORIGINAL db_table so no data migration is needed.
#
# Media policy: nothing is uploaded to this server. Videos live on
# YouTube (set to "Unlisted"), files live on Google Drive ("Anyone with
# the link" -> Viewer) or any other https host; we only store the links.
# =====================================================================


# Subject For E-Learning
class ELearningSubject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    standard = models.ForeignKey('curriculum.Standard', on_delete=models.CASCADE, related_name='subjects')
    description = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return f'{self.name} - {self.standard.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.subject_id)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'curriculum_elearningsubject'  # keep the original table — no data migration needed
        verbose_name = 'E-Learning Subjects'
        verbose_name_plural = 'E-Learning Subjects'
        ordering = ['name']
        unique_together = ('name', 'standard')


def save_lesson_files(instance, filename):
    # Kept exactly as it was in curriculum.models — not wired up as
    # Lesson.notes' upload_to (that field uses the literal string
    # 'save_lesson_files'). Preserved as-is to avoid changing behavior.
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    if instance.lesson_id:
        filename = 'lesson_files/{}.{}'.format(instance.lesson_id, instance.lesson_id, ext)
        if os.path.exists(filename):
            new_name = str(instance.lesson_id) + str('1')
            filename = 'lesson_images/{}/{}.{}'.format(instance.lesson_id, new_name, ext)

    return os.path.join(upload_to, filename)


class Lesson(models.Model):
    lesson_id = models.CharField(max_length=100, unique=True)
    standard = models.ForeignKey('curriculum.Standard', on_delete=models.CASCADE)
    subject = models.ForeignKey(ELearningSubject, on_delete=models.CASCADE, related_name='lessons')
    name = models.CharField(max_length=250, verbose_name="Topic", help_text="Enter the lesson topic (e.g. Heat Energy, Algebraic Expressions)")
    position = models.PositiveSmallIntegerField(verbose_name="Chapter no.")
    video = EmbedVideoField(
        blank=True, null=True,
        verbose_name="YouTube video link",
        help_text="Paste the YouTube link. Set the video to 'Unlisted' (not 'Private') so "
                  "students can watch without a Google account.",
    )
    # Legacy server upload — kept only so lessons that already have a file keep working.
    # New lessons should use `notes_link` instead.
    notes = models.FileField(upload_to='save_lesson_files', verbose_name="Notes", blank=True)
    # ✅ NEW — lesson file hosted externally, same approach as Assignment.resource_link
    notes_link = models.URLField(
        max_length=500, blank=True, null=True, validators=[validate_web_link],
        verbose_name="Lesson notes link (optional)",
        help_text="Link to the lesson notes/handout — e.g. a Google Drive share link "
                  "(set sharing to 'Anyone with the link' so students need no Google account). "
                  "Nothing is uploaded here.",
    )
    comment = HTMLField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        db_table = 'curriculum_lesson'  # keep the original table — no data migration needed
        ordering = ['position']
        verbose_name = 'E-Learning Lessons'
        verbose_name_plural = 'E-Learning Lessons'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('elearning:lesson_list', kwargs={'slug': self.subject.slug, 'standard': self.standard.slug})

    @property
    def html_stripped(self):
        # strip_tags(None) would return the text "None"
        return strip_tags(self.comment or '')

    @property
    def youtube_id(self):
        """11-char YouTube id parsed from `video`, or None for non-YouTube links."""
        return extract_youtube_id(self.video)

    @property
    def has_resources(self):
        return bool(self.video or self.notes_link or self.notes)


# comment module
class Comment(models.Model):
    lesson_name = models.ForeignKey(Lesson, null=True, on_delete=models.CASCADE, related_name='comments')
    comm_name = models.CharField(max_length=100, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=500)
    date_added = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.comm_name = slugify("comment by" + "-" + str(self.author) + str(self.date_added))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.comm_name

    class Meta:
        db_table = 'curriculum_comment'  # keep the original table — no data migration needed
        ordering = ['-date_added']


class Reply(models.Model):
    comment_name = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='replies')
    reply_body = models.TextField(max_length=500)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'curriculum_reply'  # keep the original table — no data migration needed
        verbose_name = 'Reply'
        verbose_name_plural = 'Replies'

    def __str__(self):
        return "reply to" + str(self.comment_name.comm_name)


# =====================================================================
# ASSIGNMENTS / HOMEWORK — external links only (no uploads)
# =====================================================================

class Assignment(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    instructions = HTMLField(
        blank=True, null=True,
        help_text="What the student needs to do for this assignment/homework."
    )
    resource_link = models.URLField(
        max_length=500, blank=True, null=True, validators=[validate_web_link],
        verbose_name="Assignment file link (optional)",
        help_text="External link to the assignment sheet/file — e.g. a Google Drive share "
                   "link or a file hosted on the school's cPanel. Nothing is uploaded here."
    )
    due_date = models.DateTimeField(blank=True, null=True)
    max_score = models.PositiveIntegerField(default=100, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='elearning_assignments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(null=True, blank=True, max_length=250, unique=True)

    class Meta:
        db_table = 'elearning_assignment'
        ordering = ['-due_date', '-created_at']
        verbose_name = 'Assignment / Homework'
        verbose_name_plural = 'Assignments / Homework'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or 'assignment'
            self.slug = base_slug
            counter = 1
            while Assignment.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                counter += 1
                self.slug = f"{base_slug}-{counter}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.lesson.name})"

    def get_absolute_url(self):
        return reverse('elearning:lesson_detail', kwargs={
            'standard': self.lesson.standard.slug,
            'subject': self.lesson.subject.slug,
            'slug': self.lesson.slug,
        })

    @property
    def is_past_due(self):
        if not self.due_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.due_date


class AssignmentSubmission(models.Model):
    """
    A student's submission for an Assignment — always an external link,
    never a server upload (Google Drive / cPanel-hosted file / YouTube).
    """
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_link = models.URLField(
        max_length=500, validators=[validate_web_link],
        help_text="Link to your completed work (Google Drive, cPanel file link, etc.)"
    )
    comment = models.TextField(max_length=500, blank=True, null=True, help_text="Optional note to your teacher")
    submitted_at = models.DateTimeField(auto_now_add=True)

    score = models.PositiveIntegerField(blank=True, null=True)
    teacher_feedback = models.TextField(max_length=500, blank=True, null=True)
    graded_at = models.DateTimeField(blank=True, null=True)
    graded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='elearning_graded_submissions')

    class Meta:
        db_table = 'elearning_assignmentsubmission'
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    def clean(self):
        super().clean()
        # Guard against typos when grading in the admin (e.g. 85 out of 10).
        if self.score is not None and self.assignment_id:
            max_score = self.assignment.max_score
            if max_score is not None and self.score > max_score:
                raise ValidationError({'score': f'Score cannot be higher than the maximum of {max_score}.'})

    def save(self, *args, **kwargs):
        # Stamp graded_at automatically the moment a score gets set.
        if self.score is not None and self.graded_at is None:
            from django.utils import timezone
            self.graded_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} - {self.assignment.title}"

    @property
    def is_graded(self):
        return self.score is not None

    @property
    def is_late(self):
        if not self.assignment.due_date:
            return False
        return self.submitted_at > self.assignment.due_date


# Teacher lesson notes — registers the models below with this app (independent feature in elearning/lessonnotes/)
from .lessonnotes.models import LessonNote, LessonNoteEvent  # noqa: E402,F401