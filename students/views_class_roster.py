"""
Class roster: list the students in ONE class, with search, pagination and CSV export.

Self-contained on purpose: it only READS from Student, so it cannot disturb any
existing view, URL, template or model.
"""
import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import urlencode
from django.utils.text import slugify

from .models import Student

# Resolve the class model from the FK instead of importing it, so this file does
# not care which app `Standard` lives in.
Standard = Student._meta.get_field("current_class").related_model

PAGE_SIZE = 25
MAX_QUERY_LENGTH = 100
EXCLUDED_CLASS_NAMES = {"", "Alumni"}  # same exclusions as the student-count page


# --------------------------------------------------------------------------
# helpers (kept pure so they are easy to unit test)
# --------------------------------------------------------------------------
def can_view_class_roster(user, standard):
    """Staff/superusers see every class; teachers only the classes assigned to them."""
    if user.is_superuser or user.is_staff:
        return True
    teacher = getattr(user, "teacher", None)
    if teacher is None:
        return False
    return teacher.standards_assigned.filter(pk=standard.pk).exists()


def build_roster_queryset(standard, query=""):
    """Enrolled students of one class, optionally narrowed by a search string.

    Every word typed must match at least one field, so "ade tunde" finds
    "Adeyemi Tunde" regardless of name order.
    """
    qs = Student.objects.enrolled().filter(current_class=standard)

    for term in query.split():
        qs = qs.filter(
            Q(first_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(USN__icontains=term)
            | Q(guardian_name__icontains=term)
            | Q(guardian_phone__icontains=term)
        )
    return qs.order_by("last_name", "first_name", "pk")


def _safe_cell(value):
    """Neutralise CSV/Excel formula injection (cells starting with = + - @)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def roster_csv_response(standard, students, query=""):
    filename = f"{slugify(standard.name) or 'class'}-students-{date.today():%Y-%m-%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")  # BOM so Excel opens UTF-8 names correctly

    writer = csv.writer(response)
    writer.writerow([f"Class: {standard.name}"] + ([f"Search: {query}"] if query else []))
    writer.writerow([
        "S/N", "USN", "Last Name", "First Name", "Middle Name", "Gender",
        "Date of Birth", "Student Type", "Status",
        "Guardian Name", "Guardian Relationship", "Guardian Phone", "Guardian Email",
    ])
    for i, s in enumerate(students.iterator(chunk_size=500), start=1):
        writer.writerow([_safe_cell(v) for v in (
            i, s.USN, s.last_name, s.first_name, s.middle_name,
            s.get_gender_display(), s.DOB, s.get_student_type_display(),
            s.get_student_status_display(),
            s.guardian_name, s.get_relationship_display(),
            s.guardian_phone, s.guardian_email,
        )])
    return response


def _back_url():
    for name in ("students:student-in-class", "students:student-list"):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return "#"


# --------------------------------------------------------------------------
# view
# --------------------------------------------------------------------------
@login_required
def class_student_list(request, class_id):
    standard = get_object_or_404(Standard, pk=class_id)

    if standard.name in EXCLUDED_CLASS_NAMES:
        messages.error(request, "That class has no active roster.")
        return redirect(_back_url())

    if not can_view_class_roster(request.user, standard):
        messages.error(request, "You are not allowed to view this class.")
        return redirect("pages:portal-home")

    query = (request.GET.get("q") or "").strip()[:MAX_QUERY_LENGTH]
    students = build_roster_queryset(standard, query)

    # CSV export uses the same filter, so "download" matches what is on screen
    if request.GET.get("export") == "csv":
        return roster_csv_response(standard, students, query)

    page_obj = Paginator(students, PAGE_SIZE).get_page(request.GET.get("page"))
    start_index = page_obj.start_index() if page_obj.paginator.count else 0

    context = {
        "standard": standard,
        "page_obj": page_obj,
        "start_index": start_index,
        "total": page_obj.paginator.count,
        "query": query,
        "q_string": urlencode({"q": query}) if query else "",  # keeps search across pages / export
        "back_url": _back_url(),
    }
    return render(request, "students/class_student_list.html", context)
