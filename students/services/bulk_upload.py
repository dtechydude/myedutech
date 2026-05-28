"""
services.py — Bulk Student Upload Business Logic
KwikSchools — Smarter Schools!

Handles CSV parsing, validation, and database operations for
bulk student creation/updating. Separated from views for testability.
"""
from __future__ import annotations
import csv
import io
import logging
from datetime import datetime, date
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError

User = get_user_model()
logger = logging.getLogger(__name__)

# ─── Field choices (mirror your model) ──────────────────────────────────────

VALID_GENDERS = {'male', 'female', 'select_gender'}
VALID_BLOOD_GROUPS = {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'select'}
VALID_GENOTYPES = {'AA', 'AS', 'SS', 'AC', 'SC', 'select'}
VALID_STUDENT_TYPES = {'day_student', 'boarder'}
VALID_STATUSES = {'active', 'inactive', 'graduated', 'dropped', 'expelled', 'suspended'}
VALID_RELATIONSHIPS = {
    'select', 'parent', 'father', 'mother', 'sister',
    'brother', 'aunt', 'uncle', 'other'
}

DATE_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y']


def _parse_date(value: str, field_name: str) -> date | None:
    """Try multiple date formats. Raise ValueError with a helpful message on failure."""
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f'Invalid date for "{field_name}": "{value}". '
        f'Use YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY.'
    )


def _clean_row(row: dict[str, Any], row_num: int) -> tuple[dict, list[str]]:
    """
    Validate and clean a single CSV row.
    Returns (cleaned_data, errors).
    """
    errors = []
    data = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

    # ── Required fields ──────────────────────────────────────────────────────
    usn = data.get('USN', '').strip()
    if not usn:
        errors.append(f'Row {row_num}: USN is required.')

    first_name = data.get('first_name', '').strip()
    if not first_name:
        errors.append(f'Row {row_num}: first_name is required.')

    last_name = data.get('last_name', '').strip()
    if not last_name:
        errors.append(f'Row {row_num}: last_name is required.')

    gender = data.get('gender', '').strip().lower()
    if gender not in VALID_GENDERS:
        errors.append(f'Row {row_num}: Invalid gender "{gender}". Use: {", ".join(VALID_GENDERS)}.')

    # ── Dates ─────────────────────────────────────────────────────────────────
    dob = None
    try:
        raw_dob = data.get('DOB', '').strip()
        if not raw_dob:
            errors.append(f'Row {row_num}: DOB is required.')
        else:
            dob = _parse_date(raw_dob, 'DOB')
    except ValueError as e:
        errors.append(str(e))

    date_admitted = None
    try:
        raw_da = data.get('date_admitted', '').strip()
        if not raw_da:
            errors.append(f'Row {row_num}: date_admitted is required.')
        else:
            date_admitted = _parse_date(raw_da, 'date_admitted')
    except ValueError as e:
        errors.append(str(e))

    # ── Optional with validation ──────────────────────────────────────────────
    student_type = data.get('student_type', 'day_student').strip().lower()
    if student_type not in VALID_STUDENT_TYPES:
        student_type = 'day_student'

    student_status = data.get('student_status', 'active').strip().lower()
    if student_status not in VALID_STATUSES:
        student_status = 'active'

    blood_group = data.get('blood_group', 'select').strip()
    if blood_group not in VALID_BLOOD_GROUPS:
        blood_group = 'select'

    genotype = data.get('genotype', 'select').strip()
    if genotype not in VALID_GENOTYPES:
        genotype = 'select'

    relationship = data.get('relationship', 'select').strip().lower()
    if relationship not in VALID_RELATIONSHIPS:
        relationship = 'select'

    cleaned = {
        'USN': usn,
        'first_name': first_name,
        'middle_name': data.get('middle_name', '').strip() or None,
        'last_name': last_name,
        'gender': gender,
        'DOB': dob,
        'blood_group': blood_group,
        'genotype': genotype,
        'health_remark': data.get('health_remark', '').strip() or 'enter health detail',
        'student_type': student_type,
        'date_admitted': date_admitted,
        'guardian_name': data.get('guardian_name', '').strip() or None,
        'guardian_phone': data.get('guardian_phone', '').strip() or None,
        'guardian_email': data.get('guardian_email', '').strip() or None,
        'guardian_address': data.get('guardian_address', '').strip() or None,
        'relationship': relationship,
        'student_status': student_status,
        # FK slugs — resolved later in the import step
        '_current_class': data.get('current_class', '').strip() or None,
        '_class_group': data.get('class_group', '').strip() or None,
    }

    return cleaned, errors


def process_student_csv(
    file_obj,
    overwrite: bool = False,
    request_user=None,
) -> dict:
    """
    Main entry point for bulk student import.

    Args:
        file_obj:       InMemoryUploadedFile from cleaned form data.
        overwrite:      If True, update existing students matched by USN.
        request_user:   The staff/admin user triggering the upload (for audit).

    Returns:
        {
          'created': int,
          'updated': int,
          'skipped': int,
          'errors': list[str],
          'total_rows': int,
        }
    """
    # Lazy imports to avoid circular imports at module level
    from students.models import Student  # adjust app label if needed

    content = file_obj.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    results = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
        'total_rows': len(rows),
    }

    # ── Pre-fetch FK lookups ──────────────────────────────────────────────────
    # Import these lazily too so this service doesn't break if models differ
    try:
        from students.models import Standard, ClassGroup  # noqa
        standard_map = {s.name.strip().lower(): s for s in Standard.objects.all()}
        class_group_map = {c.name.strip().lower(): c for c in ClassGroup.objects.all()}
    except Exception:
        standard_map = {}
        class_group_map = {}

    for i, row in enumerate(rows, start=2):  # row 1 = header
        cleaned, row_errors = _clean_row(row, i)

        if row_errors:
            results['errors'].extend(row_errors)
            results['skipped'] += 1
            continue

        usn = cleaned['USN']

        # ── Resolve FK fields ─────────────────────────────────────────────────
        current_class_obj = None
        if cleaned['_current_class']:
            current_class_obj = standard_map.get(cleaned['_current_class'].lower())
            if not current_class_obj:
                results['errors'].append(
                    f'Row {i}: Class "{cleaned["_current_class"]}" not found — skipped.'
                )
                results['skipped'] += 1
                continue

        class_group_obj = None
        if cleaned['_class_group']:
            class_group_obj = class_group_map.get(cleaned['_class_group'].lower())
            # class_group missing is a warning, not a fatal error
            if not class_group_obj:
                results['errors'].append(
                    f'Row {i} (warning): ClassGroup "{cleaned["_class_group"]}" not found — field left blank.'
                )

        # ── User account ──────────────────────────────────────────────────────
        try:
            with transaction.atomic():
                existing = Student.objects.filter(USN=usn).first()

                if existing:
                    if not overwrite:
                        results['errors'].append(
                            f'Row {i}: Student with USN "{usn}" already exists — skipped. '
                            f'Enable "Overwrite existing" to update.'
                        )
                        results['skipped'] += 1
                        continue

                    # Update existing student
                    for field in [
                        'first_name', 'middle_name', 'last_name', 'gender',
                        'DOB', 'blood_group', 'genotype', 'health_remark',
                        'student_type', 'date_admitted', 'guardian_name',
                        'guardian_phone', 'guardian_email', 'guardian_address',
                        'relationship', 'student_status',
                    ]:
                        setattr(existing, field, cleaned[field])

                    existing.current_class = current_class_obj
                    existing.class_group = class_group_obj
                    existing.save()
                    results['updated'] += 1

                else:
                    # Create Django user account
                    user, _ = User.objects.get_or_create(
                        username=usn,
                        defaults={
                            'first_name': cleaned['first_name'],
                            'last_name': cleaned['last_name'],
                            'is_active': True,
                        }
                    )

                    Student.objects.create(
                        user=user,
                        USN=usn,
                        first_name=cleaned['first_name'],
                        middle_name=cleaned['middle_name'],
                        last_name=cleaned['last_name'],
                        gender=cleaned['gender'],
                        DOB=cleaned['DOB'],
                        blood_group=cleaned['blood_group'],
                        genotype=cleaned['genotype'],
                        health_remark=cleaned['health_remark'],
                        student_type=cleaned['student_type'],
                        date_admitted=cleaned['date_admitted'],
                        guardian_name=cleaned['guardian_name'],
                        guardian_phone=cleaned['guardian_phone'],
                        guardian_email=cleaned['guardian_email'],
                        guardian_address=cleaned['guardian_address'],
                        relationship=cleaned['relationship'],
                        student_status=cleaned['student_status'],
                        current_class=current_class_obj,
                        class_group=class_group_obj,
                    )
                    results['created'] += 1

        except IntegrityError as e:
            results['errors'].append(f'Row {i}: Database error for USN "{usn}": {e}')
            results['skipped'] += 1
        except Exception as e:
            logger.exception(f'Unexpected error processing row {i} (USN={usn})')
            results['errors'].append(f'Row {i}: Unexpected error: {e}')
            results['skipped'] += 1

    return results


def generate_sample_csv() -> str:
    """
    Generate a downloadable sample CSV string with correct headers and example rows.
    """
    headers = [
        'USN', 'first_name', 'middle_name', 'last_name', 'gender', 'DOB',
        'blood_group', 'genotype', 'health_remark', 'student_type',
        'date_admitted', 'guardian_name', 'guardian_phone',
        'guardian_email', 'guardian_address', 'relationship',
        'student_status', 'current_class', 'class_group',
    ]

    sample_rows = [
        [
            'KWK2024001', 'Amara', 'Chisom', 'Okafor', 'female', '2010-05-14',
            'O+', 'AA', 'No known illness', 'day_student',
            '2024-09-01', 'Mr. Emeka Okafor', '08012345678',
            'emeka@email.com', '12 Lagos Street, Abuja', 'father',
            'active', 'JSS 1', 'JSS 1A',
        ],
        [
            'KWK2024002', 'Tunde', '', 'Adeyemi', 'male', '2009-11-22',
            'A+', 'AS', 'Mild asthma', 'boarder',
            '2024-09-01', 'Mrs. Bola Adeyemi', '08098765432',
            'bola@email.com', '5 Ibadan Road, Lagos', 'mother',
            'active', 'JSS 2', 'JSS 2B',
        ],
        [
            'KWK2024003', 'Ngozi', 'Faith', 'Eze', 'female', '2011-03-08',
            'B+', 'AA', 'Healthy', 'day_student',
            '2024-09-01', 'Dr. Kelechi Eze', '07011223344',
            '', '', 'father',
            'active', '', '',
        ],
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(sample_rows)
    return output.getvalue()
