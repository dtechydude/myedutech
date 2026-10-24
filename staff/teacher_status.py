"""
Current vs former teachers, with AUTOMATIC portal-access control.

One flag drives everything: Teacher.active.

  active = False  ->  the teacher has left the school:
                      * their portal login is switched off (user.is_active = False)
                      * date_left is filled in (today, unless a date was given)
                      * the change is written to the audit trail (TeacherStatusLog)
  active = True   ->  their login is switched back on and date_left is cleared

It works from every place that changes the flag: the front-end pages, the Django
admin tick-box or admin actions, or code - because it reacts to the save itself.

Safe by design for live schools:
  * only a CHANGE of the flag does anything. Creating a teacher, or saving other fields
    of an already-inactive teacher, never touches the login.
  * a superuser's login is never switched off by this logic.
  * bulk `.update(active=...)` skips Django signals - use the services below or the admin actions.
"""
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from curriculum.models import Standard

from .models import Teacher, TeacherStatusLog


# ------------------------------------------------------------------ signals
@receiver(pre_save, sender=Teacher)
def _remember_previous_status(sender, instance, **kwargs):
    instance._was_active = (
        sender.objects.filter(pk=instance.pk).values_list('active', flat=True).first()
        if instance.pk else None)


@receiver(post_save, sender=Teacher)
def _apply_status_change(sender, instance, created, **kwargs):
    was_active = getattr(instance, '_was_active', None)
    if created or was_active is None or was_active == instance.active:
        return  # not a status change -> never touch the login
    actor = getattr(instance, '_status_actor', None)
    if instance.active:
        _on_reactivated(instance, actor)
    else:
        reason = getattr(instance, '_status_reason', '') or instance.left_reason or ''
        _on_deactivated(instance, actor, reason)


def _set_login(user, enabled):
    """Switch a user's portal login on/off (queryset.update: no side-effect signals)."""
    if user is None:
        return
    get_user_model().objects.filter(pk=user.pk).update(is_active=enabled)
    user.is_active = enabled


def _on_deactivated(teacher, actor, reason):
    updates = {}
    if teacher.date_left is None:
        teacher.date_left = timezone.localdate()
        updates['date_left'] = teacher.date_left
    if reason and teacher.left_reason != reason[:200]:
        teacher.left_reason = reason[:200]
        updates['left_reason'] = teacher.left_reason
    if updates:
        Teacher.objects.filter(pk=teacher.pk).update(**updates)
    user = teacher.user
    if user is not None and not user.is_superuser:      # never lock out a superuser
        _set_login(user, False)
    TeacherStatusLog.objects.create(
        teacher=teacher, action=TeacherStatusLog.DEACTIVATED, reason=reason[:200],
        effective_date=teacher.date_left, changed_by=actor)


def _on_reactivated(teacher, actor):
    Teacher.objects.filter(pk=teacher.pk).update(date_left=None, left_reason='')
    teacher.date_left, teacher.left_reason = None, ''
    _set_login(teacher.user, True)
    TeacherStatusLog.objects.create(
        teacher=teacher, action=TeacherStatusLog.REACTIVATED, effective_date=timezone.localdate(),
        changed_by=actor)


# ----------------------------------------------------------------- services
def deactivate_teacher(teacher, by=None, reason='', date_left=None):
    """Mark a teacher as having left the school (switches their login off)."""
    if not teacher.active:
        raise ValidationError('This teacher is already marked as having left the school.')
    reason = (reason or '').strip()[:200]
    teacher._status_actor, teacher._status_reason = by, reason
    teacher.active, teacher.date_left, teacher.left_reason = False, date_left or timezone.localdate(), reason
    with transaction.atomic():
        teacher.save(update_fields=['active', 'date_left', 'left_reason', 'updated'])
    return teacher


def reactivate_teacher(teacher, by=None):
    """Bring a former teacher back (switches their login on again)."""
    if teacher.active:
        raise ValidationError('This teacher is already active.')
    teacher._status_actor = by
    teacher.active = True
    with transaction.atomic():
        teacher.save(update_fields=['active', 'updated'])
    return teacher


def deactivation_warnings(teacher):
    """Things the school should know BEFORE confirming that a teacher has left."""
    warnings, user = [], teacher.user
    if user is not None:
        if user.is_superuser:
            warnings.append('This is a superuser account: its login will NOT be switched off automatically.')
        elif user.is_staff:
            warnings.append('This person also has Admin (staff) rights. Those will be switched off too.')
        parent = getattr(user, 'parent', None)
        if parent is not None:
            Student = apps.get_model('students', 'Student')
            active = Student.objects.enrolled() if hasattr(Student.objects, 'enrolled') \
                else Student.objects.filter(student_status='active')
            children = active.filter(parent=parent).count()
            if children:
                warnings.append(f'This person is also the parent of {children} active student(s). '
                                'Switching off the login blocks their parent access too; they would need '
                                'a separate parent login.')
    try:
        classes = list(Standard.objects.filter(form_teacher=teacher).values_list('name', flat=True))
    except Exception:  # noqa: BLE001 - form_teacher may be modelled differently in some deployments
        classes = []
    if classes:
        warnings.append('Form teacher of: ' + ', '.join(classes) + '. Assign a new form teacher afterwards.')
    return warnings


# ------------------------------------------------------------ admin actions
@admin.action(description='Mark selected teachers as LEFT the school (switches off portal access)')
def mark_selected_former(modeladmin, request, queryset):
    done = 0
    for teacher in queryset.filter(active=True).select_related('user'):
        deactivate_teacher(teacher, by=request.user, reason='Marked as left from the admin panel')
        done += 1
    modeladmin.message_user(request, f'{done} teacher(s) marked as left; their portal access is switched off.')


@admin.action(description='Reactivate selected teachers (switches portal access back on)')
def reactivate_selected(modeladmin, request, queryset):
    done = 0
    for teacher in queryset.filter(active=False).select_related('user'):
        reactivate_teacher(teacher, by=request.user)
        done += 1
    modeladmin.message_user(request, f'{done} teacher(s) reactivated; their portal access is switched back on.')