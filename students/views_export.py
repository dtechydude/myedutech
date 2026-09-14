"""
KwikSchools — Student Export View
===================================
Exports active students to CSV for upload to the cPanel attendance portal.

CSV columns match exactly what import_students.php expects:
    usn, first_name, last_name, middle_name, current_class, guardian_phone

Add to students/urls.py:
    from .views_export import StudentCSVExportView
    path('export-for-attendance/', StudentCSVExportView.as_view(), name='export_for_attendance'),

Link in your template:
    <a href="{% url 'students:export_for_attendance' %}">Export for Attendance Portal</a>
"""

import csv
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View

from students.models import Student


def is_staff_or_super(user):
    return user.is_active and (user.is_staff or user.is_superuser)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_staff_or_super), name='dispatch')
class StudentCSVExportView(View):
    """
    Exports all active students in the format required by
    the KwikSchools cPanel attendance portal (import_students.php).

    Filters: only students with student_status='active' and a current_class set.
    Teachers without a guardian_phone fallback to an empty string
    so the row is still included (phone can be added later in cPanel).
    """

    def get(self, request):
        # Build queryset — only active students with a class assigned
        qs = (
            Student.objects
            .filter(student_status='active', current_class__isnull=False)
            .select_related('current_class')
            .order_by('current_class__name', 'last_name', 'first_name')
        )

        # Optional filter: single class
        class_id = request.GET.get('class_id')
        if class_id:
            qs = qs.filter(current_class_id=class_id)

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="kwikschools_students_export.csv"'
        )

        # UTF-8 BOM so Excel opens it correctly on Windows
        response.write('\xef\xbb\xbf')

        writer = csv.writer(response)

        # Header — must match import_students.php expected columns exactly
        writer.writerow([
            'usn',
            'first_name',
            'last_name',
            'middle_name',
            'current_class',
            'guardian_phone',
        ])

        for student in qs:
            # guardian_phone: prefer guardian_phone field; fall back to empty
            phone = (student.guardian_phone or '').strip()

            writer.writerow([
                student.USN,
                student.first_name,
                student.last_name,
                student.middle_name or '',
                student.current_class.name if student.current_class else '',
                phone,
            ])

        return response
