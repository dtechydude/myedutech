from __future__ import annotations
from users.models import Profile  # ← change if your app is named differently


"""
services/bulk_photos.py — Bulk Profile Photo Upload Logic  (REFACTORED)
KwikSchools — Smarter Schools!

Root cause fixes:
  1. Profile.user_type filter was the wrong approach — Student/Teacher/Parent
     each live in their OWN model, not guaranteed to have a matching Profile
     with user_type set correctly.  We now query each domain model directly.
  2. Standard lives in the `curriculum` app, not `students`.
  3. Teacher.get_full_name() uses self.user.last_name / self.user.first_name,
     not self.last_name / self.first_name.
  4. Added USN to student dicts so the grid can show it.
  5. "All users" option: pass user_type='all' to get every active profile.
  6. Graceful error logging so silent except: pass never hides real problems.
"""
# from __future__ import annotations

import logging
import os

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()
logger = logging.getLogger(__name__)

MAX_SIZE_BYTES    = 100 * 1024   # 100 KB
ALLOWED_EXT       = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_MIME      = {'image/jpeg', 'image/png', 'image/webp'}


# ── Image validation ──────────────────────────────────────────────────────────

def _ext(name: str) -> str:
    return os.path.splitext(name.lower())[1]


def validate_single_image(file) -> list:
    errors = []
    if _ext(file.name) not in ALLOWED_EXT:
        errors.append(f'"{file.name}" — unsupported format. Use JPG, PNG or WEBP.')
    if hasattr(file, 'content_type') and file.content_type not in ALLOWED_MIME:
        errors.append(f'"{file.name}" — invalid MIME type ({file.content_type}).')
    if file.size > MAX_SIZE_BYTES:
        errors.append(
            f'"{file.name}" — {file.size/1024:.1f} KB exceeds the 100 KB limit. '
            f'Please compress the image and retry.'
        )
    return errors


# ── Profile helper ────────────────────────────────────────────────────────────

def _get_profile_model():
    """Import Profile from whichever app name is used in this project."""
    for app in ('accounts', 'users', 'profiles'):
        try:
            module = __import__(f'{app}.models', fromlist=['Profile'])
            return module.Profile
        except (ImportError, AttributeError):
            continue
    raise ImportError(
        'Cannot find Profile model. Update _get_profile_model() in bulk_photos.py '
        'to match your app name.'
    )


def _photo_url(profile) -> str | None:
    """Safely return the URL of a profile image, or None."""
    try:
        if profile and profile.image:
            return profile.image.url
    except Exception:
        pass
    return None


def _profile_map(user_ids: list) -> dict:
    """Return {user_id: profile} for a list of user PKs."""
    Profile = _get_profile_model()
    return {
        p.user_id: p
        for p in Profile.objects.filter(user_id__in=user_ids).select_related('user')
    }


# ── Class choices (Standard lives in curriculum app) ─────────────────────────

def get_class_choices() -> list:
    """
    Return [(pk, name), ...] for all Standard objects.
    Standard is in the `curriculum` app.
    """
    for app in ('curriculum', 'students', 'school'):
        try:
            module = __import__(f'{app}.models', fromlist=['Standard'])
            Standard = module.Standard
            return [(s.pk, str(s)) for s in Standard.objects.order_by('name')]
        except (ImportError, AttributeError):
            continue
    logger.warning('get_class_choices: Could not find Standard model in any known app.')
    return []


# ── Per-type user fetchers ────────────────────────────────────────────────────

def _fetch_students(class_filter_pk: int | None) -> list:
    """
    Query the Student model directly.
    Returns list of user dicts ready for JSON serialisation.
    """
    try:
        from students.models import Student
    except ImportError:
        logger.error('_fetch_students: cannot import students.models.Student')
        return []

    qs = (
        Student.objects
        .select_related('user', 'current_class', 'class_group')
        .filter(user__isnull=False, user__is_active=True)
        .exclude(student_status='graduated')
        .exclude(student_status='dropped')
        .exclude(student_status='expelled')
    )

    if class_filter_pk:
        qs = qs.filter(current_class_id=class_filter_pk)

    qs = qs.order_by('last_name', 'first_name')

    user_ids  = [s.user_id for s in qs]
    prof_map  = _profile_map(user_ids)

    results = []
    for student in qs:
        u = student.user

        # Build full name from Student model fields (source of truth)
        names     = [student.last_name, student.first_name, student.middle_name]
        full_name = ' '.join(filter(None, names)).strip() or u.username

        # Class label
        class_label = str(student.current_class) if student.current_class else 'No Class'
        group_label = str(student.class_group)   if student.class_group  else ''
        label       = f'{class_label}' + (f' · {group_label}' if group_label else '')

        profile   = prof_map.get(u.pk)
        photo_url = _photo_url(profile)

        results.append({
            'user_id':      u.pk,
            'username':     u.username,
            'usn':          student.USN,
            'full_name':    full_name,
            'user_type':    'student',
            'label':        label,
            'current_photo': photo_url,
            'status':       student.student_status,
        })

    return results


def _fetch_teachers() -> list:
    """
    Query the Teacher model directly.
    Teacher.get_full_name() uses user.last_name / user.first_name.
    """
    try:
        from teachers.models import Teacher
    except ImportError:
        try:
            from staff.models import Teacher
        except ImportError:
            logger.error('_fetch_teachers: cannot find Teacher model in teachers or staff app')
            return []

    qs = (
        Teacher.objects
        .select_related('user', 'dept', 'staff_role')
        .filter(user__isnull=False, user__is_active=True)
        .order_by('last_name', 'first_name')
    )

    user_ids = [t.user_id for t in qs]
    prof_map = _profile_map(user_ids)

    results = []
    for teacher in qs:
        u = teacher.user

        # get_full_name() uses user.last_name etc — replicate safely here
        names     = [u.last_name, u.first_name, teacher.middle_name]
        full_name = ' '.join(filter(None, names)).strip() or u.username

        dept_label = str(teacher.dept) if teacher.dept else ''
        role_label = str(teacher.staff_role) if teacher.staff_role else 'Teacher'
        label      = role_label + (f' · {dept_label}' if dept_label else '')

        profile   = prof_map.get(u.pk)
        photo_url = _photo_url(profile)

        results.append({
            'user_id':       u.pk,
            'username':      u.username,
            'usn':           u.username,   # teachers don't have a USN field
            'full_name':     full_name,
            'user_type':     'teacher',
            'label':         label,
            'current_photo': photo_url,
            'status':        'active' if teacher.active else 'inactive',
        })

    return results


def _fetch_parents() -> list:
    """
    Query Parent model. Falls back to Profile(user_type='parent') if no
    dedicated Parent model is available.
    """
    # Try dedicated Parent model first
    for app in ('parents', 'students', 'accounts'):
        try:
            module = __import__(f'{app}.models', fromlist=['Parent'])
            Parent = module.Parent
            qs = (
                Parent.objects
                .select_related('user')
                .filter(user__isnull=False, user__is_active=True)
            )

            user_ids = [p.user_id for p in qs if p.user_id]
            prof_map = _profile_map(user_ids)

            results = []
            for parent in qs:
                if not parent.user_id:
                    continue
                u = parent.user
                full_name = f'{u.last_name} {u.first_name}'.strip() or u.username

                # Try common name fields on Parent model
                for attr in ('get_full_name', 'name', 'full_name'):
                    try:
                        val = getattr(parent, attr)
                        if callable(val):
                            val = val()
                        if val and val.strip():
                            full_name = val.strip()
                            break
                    except Exception:
                        pass

                profile   = prof_map.get(u.pk)
                photo_url = _photo_url(profile)

                results.append({
                    'user_id':       u.pk,
                    'username':      u.username,
                    'usn':           u.username,
                    'full_name':     full_name,
                    'user_type':     'parent',
                    'label':         'Parent',
                    'current_photo': photo_url,
                    'status':        'active',
                })
            return results

        except (ImportError, AttributeError):
            continue

    # Fallback: Profile with user_type='parent'
    logger.warning('_fetch_parents: no Parent model found, falling back to Profile queryset.')
    Profile   = _get_profile_model()
    profiles  = (
        Profile.objects
        .select_related('user')
        .filter(user_type='parent', user__is_active=True)
        .order_by('user__last_name')
    )

    results = []
    for p in profiles:
        u = p.user
        results.append({
            'user_id':       u.pk,
            'username':      u.username,
            'usn':           u.username,
            'full_name':     f'{u.last_name} {u.first_name}'.strip() or u.username,
            'user_type':     'parent',
            'label':         'Parent',
            'current_photo': _photo_url(p),
            'status':        'active',
        })
    return results


def _fetch_all() -> list:
    """Return students + teachers + parents combined, deduplicated by user_id."""
    seen     = set()
    combined = []
    for row in (_fetch_students(None) + _fetch_teachers() + _fetch_parents()):
        uid = row['user_id']
        if uid not in seen:
            seen.add(uid)
            combined.append(row)
    combined.sort(key=lambda r: r['full_name'].lower())
    return combined


# ── Public entry point ────────────────────────────────────────────────────────

def get_users_for_type(user_type: str, class_filter_pk: int | None = None) -> list:
    """
    Public function called by views.

    user_type: 'student' | 'teacher' | 'parent' | 'all'
    class_filter_pk: Standard.pk — only used when user_type == 'student'
    """
    dispatch = {
        'student': lambda: _fetch_students(class_filter_pk),
        'teacher': _fetch_teachers,
        'parent':  _fetch_parents,
        'all':     _fetch_all,
    }
    fn = dispatch.get(user_type)
    if fn is None:
        logger.error(f'get_users_for_type: unknown user_type "{user_type}"')
        return []
    try:
        return fn()
    except Exception as e:
        logger.exception(f'get_users_for_type({user_type}) failed: {e}')
        return []


# ── Save photos ───────────────────────────────────────────────────────────────

def save_bulk_photos(files_map: dict) -> dict:
    """
    Process { 'photo_<user_id>': UploadedFile } from request.FILES.

    Returns { 'saved': int, 'skipped': int, 'errors': list[dict] }
    """
    Profile = _get_profile_model()
    results = {'saved': 0, 'skipped': 0, 'errors': []}

    for key, uploaded_file in files_map.items():
        if not key.startswith('photo_'):
            continue

        try:
            user_id = int(key.split('photo_', 1)[1])
        except (ValueError, IndexError):
            continue

        # Server-side validation (client already checked, but never trust client)
        file_errors = validate_single_image(uploaded_file)
        if file_errors:
            try:
                username = User.objects.get(pk=user_id).username
            except User.DoesNotExist:
                username = f'user_{user_id}'
            for err in file_errors:
                results['errors'].append({'user_id': user_id, 'username': username, 'message': err})
            results['skipped'] += 1
            continue

        try:
            with transaction.atomic():
                try:
                    profile = Profile.objects.select_for_update().get(user_id=user_id)
                except Profile.DoesNotExist:
                    # Auto-create profile if missing (edge case)
                    u = User.objects.get(pk=user_id)
                    profile = Profile.objects.create(user=u)
                    logger.info(f'save_bulk_photos: created missing Profile for user_id={user_id}')

                # Remove old image from disk to save space
                if profile.image:
                    try:
                        old_path = profile.image.path
                        if os.path.isfile(old_path):
                            os.remove(old_path)
                    except Exception:
                        pass  # non-fatal

                profile.image = uploaded_file
                profile.save(update_fields=['image'])
                results['saved'] += 1

        except User.DoesNotExist:
            results['errors'].append({
                'user_id': user_id,
                'username': f'user_{user_id}',
                'message': f'User with ID {user_id} does not exist.',
            })
            results['skipped'] += 1
        except Exception as e:
            logger.exception(f'save_bulk_photos: failed for user_id={user_id}')
            results['errors'].append({
                'user_id': user_id,
                'username': f'user_{user_id}',
                'message': f'Unexpected error: {e}',
            })
            results['skipped'] += 1

    return results
