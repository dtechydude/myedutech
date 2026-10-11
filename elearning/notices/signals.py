"""Automatic notifications for the existing elearning models (no view changes needed)."""
import logging
from functools import partial

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from . import services
from .models import Notification

logger = logging.getLogger(__name__)


def _safely(func):
    """Run a notification job; never let it break the save that triggered it."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:  # noqa: BLE001
            logger.exception('Notification job failed: %s', func.__name__)
    wrapper.__name__ = func.__name__
    return wrapper


def lesson_url(lesson):
    try:
        return reverse('elearning:lesson_detail', kwargs={
            'standard': lesson.standard.slug, 'subject': lesson.subject.slug, 'slug': lesson.slug})
    except NoReverseMatch:
        return ''


# --------------------------------------------------------------- new lesson
@receiver(post_save, sender='elearning.Lesson')
def lesson_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(partial(_notify_new_lesson, instance.pk))


@_safely
def _notify_new_lesson(lesson_pk):
    Lesson = apps.get_model('elearning', 'Lesson')
    lesson = Lesson.objects.select_related('standard', 'subject').filter(pk=lesson_pk).first()
    if lesson is None:
        return
    services.notify(
        services.students_of_class(lesson.standard), Notification.Category.LESSON,
        'New lesson available', f'{lesson.subject.name}: {lesson.name}',
        url=lesson_url(lesson), dedupe_key=f'lesson-{lesson.pk}')


# ----------------------------------------------------------- new assignment
@receiver(post_save, sender='elearning.Assignment')
def assignment_created(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(partial(_notify_new_assignment, instance.pk))


@_safely
def _notify_new_assignment(assignment_pk):
    Assignment = apps.get_model('elearning', 'Assignment')
    a = Assignment.objects.select_related('lesson__standard', 'lesson__subject').filter(pk=assignment_pk).first()
    if a is None:
        return
    due = (f'Due {timezone.localtime(a.due_date):%a, %b %d at %I:%M %p}' if a.due_date else 'No due date')
    services.notify(
        services.students_of_class(a.lesson.standard), Notification.Category.ASSIGNMENT,
        f'New assignment: {a.title}', f'{a.lesson.subject.name} · {due}',
        url=lesson_url(a.lesson) + '#homework-section', dedupe_key=f'assignment-{a.pk}')


# ------------------------------------------------------------- graded work
@receiver(pre_save, sender='elearning.AssignmentSubmission')
def remember_previous_score(sender, instance, **kwargs):
    instance._previous_score = None
    if instance.pk:
        instance._previous_score = sender.objects.filter(pk=instance.pk).values_list('score', flat=True).first()


@receiver(post_save, sender='elearning.AssignmentSubmission')
def submission_graded(sender, instance, created, **kwargs):
    if instance.score is not None and instance.score != getattr(instance, '_previous_score', None):
        transaction.on_commit(partial(_notify_graded, instance.pk))


@_safely
def _notify_graded(submission_pk):
    Submission = apps.get_model('elearning', 'AssignmentSubmission')
    s = Submission.objects.select_related('assignment__lesson__standard', 'assignment__lesson__subject').filter(
        pk=submission_pk).first()
    if s is None or s.score is None:
        return
    total = f'/{s.assignment.max_score}' if s.assignment.max_score else ''
    services.notify(
        get_user_model().objects.filter(student__pk=s.student_id), Notification.Category.GRADE,
        f'Graded: {s.assignment.title}', f'You scored {s.score}{total}.',
        url=lesson_url(s.assignment.lesson) + '#homework-section', dedupe_key=f'graded-{s.pk}-{s.score}')