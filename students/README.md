# KwikSchools — Bulk Student Upload

## Files Delivered

| File | Purpose |
|------|---------|
| `students/forms.py` | `StudentBulkUploadForm` — validates file type, size, and required CSV headers |
| `students/services.py` | `process_student_csv()` — full import logic (validate, create/update, FK resolution) |
| `students/views.py` | `StudentBulkUploadView`, `download_sample_csv`, `ajax_validate_csv_headers` |
| `students/urls.py` | URL routes for all three views |
| `students/templates/students/bulk_upload.html` | Full mobile-first UI template |
| `students/management/commands/import_students.py` | CLI command for server-side imports |

---

## Integration Steps

### 1. Wire up URLs

In your project's main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... other urls
    path('students/', include('students.urls', namespace='students')),
]
```

### 2. Verify your `login` URL name

The views redirect unauthenticated users to `login`. Confirm your login URL is named `login` in your urls.py, or update the `login_url` parameter in `views.py`:

```python
# views.py — change this if your login URL has a different name
staff_required = user_passes_test(_is_staff_or_superuser, login_url='accounts:login')
```

### 3. Confirm your Student app label

`services.py` imports from `students.models`. If your app is named differently, update:

```python
# services.py
from your_app_name.models import Student, Standard, ClassGroup
```

### 4. Template inheritance (optional)

The template is fully standalone (no base template required). To extend your existing layout, replace the `<html>...<body>` wrapper with:

```html
{% extends "base.html" %}
{% block content %}
  <!-- paste the <main class="page">...</main> block here -->
{% endblock %}
```

---

## Accessing the Upload Page

| URL | View |
|-----|------|
| `/students/bulk-upload/` | Upload form (GET) / process upload (POST) |
| `/students/bulk-upload/sample-csv/` | Download CSV template |
| `/students/bulk-upload/validate-headers/` | AJAX header pre-check |

Only users with `is_staff=True` or `is_superuser=True` can access these URLs.

---

## CSV Format

### Required Columns
`USN`, `first_name`, `last_name`, `gender`, `DOB`, `student_type`, `date_admitted`

### Optional Columns
`middle_name`, `blood_group`, `genotype`, `health_remark`, `student_type`, `guardian_name`,
`guardian_phone`, `guardian_email`, `guardian_address`, `relationship`, `student_status`,
`current_class`, `class_group`

### Date Formats Accepted
- `YYYY-MM-DD` (recommended)
- `DD/MM/YYYY`
- `DD-MM-YYYY`
- `MM/DD/YYYY`

### Valid Field Values

| Field | Valid values |
|-------|-------------|
| `gender` | `male`, `female`, `select_gender` |
| `student_type` | `day_student`, `boarder` |
| `student_status` | `active`, `inactive`, `graduated`, `dropped`, `expelled`, `suspended` |
| `blood_group` | `A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-` |
| `genotype` | `AA`, `AS`, `SS`, `AC`, `SC` |
| `relationship` | `parent`, `father`, `mother`, `sister`, `brother`, `aunt`, `uncle`, `other` |
| `current_class` | Must match exactly a `Standard.name` in the database |
| `class_group` | Must match exactly a `ClassGroup.name` in the database |

---

## CLI Import (for large batches / server-side imports)

```bash
# Normal import
python manage.py import_students /path/to/students.csv

# Overwrite existing students matched by USN
python manage.py import_students /path/to/students.csv --overwrite

# Dry-run — validate without saving
python manage.py import_students /path/to/students.csv --dry-run
```

---

## Behaviour

| Scenario | Default | With `--overwrite` / toggle on |
|----------|---------|-------------------------------|
| USN already exists | Skip + log warning | Update the existing student record |
| Class name not found | Skip row with error | — |
| ClassGroup not found | Warning, field left blank | — |
| Invalid date format | Skip row with error | — |
| Missing required column | Entire upload rejected | — |
| File > 5 MB | Form validation error | — |
| More than 1,000 rows | Form validation error | — |

---

## Security

- Views are protected by `@login_required` + `user_passes_test(is_staff or is_superuser)`.
- CSRF token is required for all POST requests.
- File extension and size are validated before any processing.
- Each row is wrapped in `transaction.atomic()` so one bad row never partially corrupts a student record.
- SQL injection is impossible — all DB writes go through Django ORM.
