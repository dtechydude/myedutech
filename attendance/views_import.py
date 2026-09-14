"""
KwikSchools — Attendance CSV Import View
=========================================
Imports the CSV exported from the PHP cPanel attendance portal
and updates AttendanceSummary + Attendance records in Django.

CSV columns (from export.php):
    usn, full_name, class_name, attend_date, status, method, marked_at

Mapping:
─────────────────────────────────────────────────────────────
CSV column    │ Django action
─────────────────────────────────────────────────────────────
usn           │ Student.USN  (lookup key — never written)
attend_date   │ Attendance.date
status        │ present/late → present=True  |  absent → False
              │ AttendanceSummary.days_present recalculated
              │ from all present days in the term after import
─────────────────────────────────────────────────────────────

Place at:  attendance/views_import.py
URL:       path('import-csv/', AttendanceCSVImportView.as_view(), name='import_csv')
"""

import csv
import io
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View

from students.models import Student
from curriculum.models import Session, Term
from .models import Attendance, AttendanceSummary


def is_staff_or_super(user):
    return user.is_active and (user.is_staff or user.is_superuser)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_staff_or_super), name='dispatch')
class AttendanceCSVImportView(View):
    """
    GET  → render upload form
    POST → process CSV, update Attendance + AttendanceSummary
    """
    template_name = 'attendance/import_csv.html'

    def get(self, request):
        return render(request, self.template_name, {
            'sessions': Session.objects.all().order_by('-id'),
            'terms':    Term.objects.all().order_by('id'),
        })

    def post(self, request):
        session_id = request.POST.get('session_id')
        term_id    = request.POST.get('term_id')
        csv_file   = request.FILES.get('csv_file')

        # ── Validation ──────────────────────────────────────────────────────
        errors = []
        if not session_id:  errors.append('Please select a Session.')
        if not term_id:     errors.append('Please select a Term.')
        if not csv_file:    errors.append('Please upload a CSV file.')
        elif not csv_file.name.endswith('.csv'):
            errors.append('File must be a .csv file.')
        for err in errors:
            messages.error(request, err)
        if errors:
            return redirect('attendance:import_csv')

        try:
            session = Session.objects.get(pk=session_id)
            term    = Term.objects.get(pk=term_id)
        except (Session.DoesNotExist, Term.DoesNotExist):
            messages.error(request, 'Invalid session or term.')
            return redirect('attendance:import_csv')

        # ── Parse CSV ───────────────────────────────────────────────────────
        try:
            decoded = csv_file.read().decode('utf-8-sig')  # strips BOM
            reader  = csv.DictReader(io.StringIO(decoded))
            rows    = list(reader)
        except Exception as exc:
            messages.error(request, f'Could not read CSV: {exc}')
            return redirect('attendance:import_csv')

        if not rows:
            messages.warning(request, 'CSV file is empty.')
            return redirect('attendance:import_csv')

        required_cols = {'usn', 'attend_date', 'status'}
        actual_cols   = set(rows[0].keys())
        missing       = required_cols - actual_cols
        if missing:
            messages.error(request, f'CSV missing columns: {", ".join(missing)}')
            return redirect('attendance:import_csv')

        # ── Process ─────────────────────────────────────────────────────────
        created  = updated = skipped = 0
        warnings = []
        student_cache: dict[str, Student] = {}

        with transaction.atomic():
            for i, row in enumerate(rows, start=2):
                usn        = (row.get('usn')         or '').strip()
                raw_date   = (row.get('attend_date') or '').strip()
                raw_status = (row.get('status')      or '').strip().lower()

                if not usn or not raw_date or not raw_status:
                    skipped += 1
                    continue

                # Resolve student via USN
                if usn not in student_cache:
                    try:
                        student_cache[usn] = Student.objects.get(USN=usn)
                    except Student.DoesNotExist:
                        warnings.append(f'Row {i}: USN "{usn}" not found — skipped.')
                        skipped += 1
                        continue

                student = student_cache[usn]

                from datetime import date as date_type
                try:
                    attend_date = date_type.fromisoformat(raw_date)
                except ValueError:
                    warnings.append(f'Row {i}: bad date "{raw_date}" — skipped.')
                    skipped += 1
                    continue

                # present/late → True;  absent → False
                is_present = raw_status in ('present', 'late')

                obj, was_created = Attendance.objects.update_or_create(
                    student=student,
                    date=attend_date,
                    defaults={'present': is_present},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            # ── Recalculate AttendanceSummary for every affected student ────
            for student in student_cache.values():
                qs = Attendance.objects.filter(student=student, present=True)

                # Scope to term date range if Term model has those fields
                if hasattr(term, 'start_date') and term.start_date:
                    qs = qs.filter(date__gte=term.start_date)
                if hasattr(term, 'end_date') and term.end_date:
                    qs = qs.filter(date__lte=term.end_date)

                days_present = qs.count()

                AttendanceSummary.objects.update_or_create(
                    student=student,
                    session=session,
                    term=term,
                    defaults={
                        'days_present': days_present,
                        'entered_by':   request.user,
                        'remarks':      'Auto-imported from KwikSchools Attendance Portal.',
                    },
                )

        messages.success(
            request,
            f'Import complete — {created} created, {updated} updated, {skipped} skipped.'
        )
        for w in warnings[:10]:
            messages.warning(request, w)
        if len(warnings) > 10:
            messages.warning(request, f'… and {len(warnings)-10} more skipped rows.')

        return redirect('attendance:import_csv')
