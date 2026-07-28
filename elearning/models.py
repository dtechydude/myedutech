from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.urls import reverse
import os
from django.utils.html import strip_tags
from embed_video.fields import EmbedVideoField
from tinymce.models import HTMLField

# =====================================================================
# ✅ E-LEARNING APP — fully independent
# ---------------------------------------------------------------------
# This app is standalone: its own namespace ('elearning', not
# 'curriculum'), its own URL prefix, its own templates folder, and no
# Python-level imports of `curriculum` anywhere in this app's code.
#
# The ONE unavoidable link: a Lesson/ELearningSubject has to belong to
# some class, and "class" (Standard) is owned by `curriculum` as the
# single source of truth for the school's class list — duplicating that
# model here would create two disagreeing copies of the same data, which
# is worse than a schema relationship. That link is expressed as a lazy
# 'curriculum.Standard' string on the FK fields below (Django resolves
# this through the app registry at query time — no `import curriculum...`
# anywhere in this file), and in views.py, where the 3 views that list
# classes fetch the Standard model via `django.apps.apps.get_model(...)`
# rather than a top-level import. This is a schema/data dependency, not a
# code dependency — elearning's own logic never reaches into curriculum's
# views, forms, or admin, and curriculum has no knowledge of elearning at
# all (no re-exports, no shims — this app was previously delivered with
# backward-compatible re-exports in curriculum for a transition period;
# those have been removed here in favor of full independence, per your
# request. If anything else in your project still does
# `from curriculum.models import Lesson` or `{% url 'curriculum:lesson_detail' %}`,
# see the README for what to update).
#
# IMPORTANT — data continuity (unrelated to app independence):
# ELearningSubject / Lesson / Comment / Reply are UNCHANGED in every
# field/behavior from their previous home in curriculum/models.py. Each
# one has an explicit Meta.db_table pointing at its ORIGINAL table name
# (e.g. 'curriculum_lesson') — that's just where the data already
# physically lives in your database; it has nothing to do with which
# app "owns" the Python code. See the migration notes in the README
# before running `migrate`.
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
    # Kept exactly as it was in curriculum.models — note this function is
    # NOT actually wired up as Lesson.notes' upload_to (that field uses
    # the literal string 'save_lesson_files' as its upload_to, not this
    # function reference), so it currently has no effect. Preserved as-is
    # to avoid changing existing behavior; safe to clean up separately.
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
    video = EmbedVideoField(blank=True, null=True)
    notes = models.FileField(upload_to='save_lesson_files', verbose_name="Notes", blank=True)
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
        return strip_tags(self.comment)


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

    def __str__(self):
        return "reply to" + str(self.comment_name.comm_name)


# =====================================================================
# ✅ NEW — ASSIGNMENTS / HOMEWORK
# ---------------------------------------------------------------------
# Deliberately simple, k-12-appropriate, and file-upload-free:
#   - Teachers post an assignment with instructions and (optionally) a
#     link to the assignment file/sheet hosted externally — Google Drive,
#     a cPanel-hosted file, etc. Nothing is stored on this server.
#   - Students submit their own external link (Google Drive, cPanel, a
#     doc shared link, etc.) plus an optional note — again, no file ever
#     touches this server.
#   - Grading (score + feedback) is done by teachers/staff — simplest
#     path is directly through Django admin (AssignmentSubmission is
#     registered there with score/feedback editable inline), so no new
#     grading UI/package is required. A dedicated grading page can be
#     added later if wanted.
# =====================================================================

class Assignment(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    instructions = HTMLField(
        blank=True, null=True,
        help_text="What the student needs to do for this assignment/homework."
    )
    resource_link = models.URLField(
        max_length=500, blank=True, null=True,
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
            # keep it globally unique even if two lessons have a similarly
            # titled assignment — avoids any ambiguity when looking one up
            # by slug alone (the same pattern Lesson relies on already).
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
    never a server upload, per the school's hosting preference (Google
    Drive / cPanel-hosted files / YouTube for any video work).
    """
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_link = models.URLField(
        max_length=500,
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

    def save(self, *args, **kwargs):
        # Stamp graded_at automatically the moment a score gets set,
        # without requiring a separate grading view/form.
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
