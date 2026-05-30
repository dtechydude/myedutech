# KwikSchools — Prep Report Card Module
## Setup & Integration Guide

---

## 1. Overview

The `prep_reports` app adds a **checklist-style report card** system for preparatory
classes (Pre-Nursery, Nursery, KG, Reception, etc.).  
Unlike the numeric scoring system, teachers tick columns (e.g. A/B/C/D/E or
Apprentice / Practitioner / Expert) for each skill/learning objective.

### Key design decisions
| Concern | How it's handled |
|---|---|
| Which classes use this system | Admin flags a `Standard` as a `PrepClass` |
| Rating columns (A/B/C, Apprentice/Expert…) | Configurable `RatingScale` + `RatingColumn` |
| Teacher restriction (own subjects/classes only) | `services.py` checks `teacher_profile.assigned_classes` and `assigned_subjects` |
| Form-teacher-only domain ratings | `user_can_edit_domain_ratings()` checks `standard.form_teacher` |
| Superuser / is_staff bypass | Both helpers short-circuit for superuser/staff |
| Workflow | draft → submitted → approved → published |
| PDF export | WeasyPrint (preferred) or browser print fallback |

---

## 2. Installation

### 2a. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    ...
    'prep_reports',
]
```

### 2b. Add to main urls.py

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    ...
    path('prep-reports/', include('prep_reports.urls', namespace='prep_reports')),
]
```

### 2c. Run migrations

```bash
python manage.py makemigrations prep_reports
python manage.py migrate
```

---

## 3. Dependencies

```
# requirements.txt additions
weasyprint>=60.0        # PDF generation (optional but recommended)
```

Install:
```bash
pip install weasyprint
```

WeasyPrint requires system libraries. On Ubuntu/Debian:
```bash
sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
  libffi-dev libjpeg-dev libopenjp2-7-dev
```

---

## 4. Admin Setup (one-time configuration)

### Step 1: Create a Rating Scale

Admin → Prep Reports → Rating Scales → Add

Example A (PurpleStars style):
- Name: `A-E Scale`
- Is Default: ✓
- Columns: A (order 1), B (order 2), C (order 3), D (order 4), E (order 5)

Example B (Watford style):
- Name: `Mastery Scale`
- Columns: Apprentice (order 1), Practitioner (order 2), Expert (order 3)

### Step 2: Flag classes as Prep Classes

Admin → Prep Reports → Prep Class Configurations → Add

Pick each `Standard` that uses the checklist system (Pre-Nursery A, Nursery B, etc.)

### Step 3: Add Subject Skills

Admin → Prep Reports → Prep Subject Skills → Add

For each subject (Numeracy, Literacy, etc.) add the observable skill statements.
- Subject: Numeracy
- Description: "The child is able to count 1–100 on the number chart"
- Prep Class: (leave blank to apply to all prep classes, OR select one specific class)
- Order: 1

### Step 4: Configure Domain Trait Templates

Admin → Prep Reports → Domain Trait Templates → Add (or via Prep Class inline)

These auto-populate blank domain rating rows when report cards are created.

Psychomotor examples: Punctuality, Neatness, Handwriting, Verbal Fluency, Games, Sports
Affective examples: Honesty, Relationship With Staff, Behaviour, Attentiveness

### Step 5: Create an Academic Period

Admin → Prep Reports → Prep Academic Periods → Add

- Session: 2024/2025
- Term: 3
- Days School Opened: 102
- Next Term Begins: 15/09/2025
- Is Current: ✓

---

## 5. Teacher Relationship Requirements

The permission system assumes your `Teacher` model has:

```python
# In your teacher/staff app
class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='teacher_profile')
    assigned_classes = models.ManyToManyField('curriculum.Standard', blank=True)
    assigned_subjects = models.ManyToManyField('curriculum.Subject', blank=True)

# And for form-teacher check, your Standard should have:
class Standard(models.Model):
    ...
    form_teacher = models.ForeignKey(Teacher, null=True, blank=True,
                                     on_delete=models.SET_NULL,
                                     related_name='form_class')
```

If your model uses different field names, update `services.py`:
```python
# services.py — update these lines to match your Teacher model:
assigned_standards = teacher_profile.assigned_classes.values_list('id', flat=True)
assigned_subjects  = teacher_profile.assigned_subjects.values_list('id', flat=True)

# And for form teacher:
standard.form_teacher == teacher_profile
```

---

## 6. Creating Report Cards

### Via Admin (bulk)
1. Navigate to Prep Reports → Prep Report Cards → Add
2. Or use the bulk-create button on the class student list page (staff only)

### Via Portal (recommended workflow)
1. Admin/staff goes to `/prep-reports/`
2. Selects the prep class and period
3. Clicks **Bulk Create** — this auto-generates one report card per enrolled student
   with blank skill entries and domain rating rows pre-populated from templates

---

## 7. Teacher Workflow

1. Teacher logs in → navigates to `/prep-reports/`
2. Sees only their assigned prep classes
3. Clicks **View Students** → sees all students and report card statuses
4. Clicks **✏ Edit** on a student
5. Switches between subject tabs and ticks the appropriate columns
6. Saves each subject, adds comments
7. If form teacher: enters psychomotor & affective domain ratings
8. Clicks **Submit for Approval** when done

---

## 8. Admin Approval Workflow

1. Admin navigates to the report card edit page (or uses Django Admin bulk actions)
2. Clicks **Approve** (status: submitted → approved)
3. Clicks **Publish** (status: approved → published) — parents can now view

---

## 9. PDF Export

Navigate to `/prep-reports/report/<id>/pdf/`  
Requires WeasyPrint. If not installed, falls back to a printable HTML page.

To add school logo/name to the PDF, pass them via a context processor:
```python
# context_processors.py
def school_settings(request):
    return {
        'school_name': settings.SCHOOL_NAME,
        'school_address': settings.SCHOOL_ADDRESS,
        'school_phone': settings.SCHOOL_PHONE,
        'school_email': settings.SCHOOL_EMAIL,
        'school_motto': settings.SCHOOL_MOTTO,
    }
```

---

## 10. Integration with Existing Results App

The `PrepDomainRating` model stores psychomotor/affective ratings inline with
the report card. If you want to also sync with the existing `MotorAbilityScore`
model in your `results` app, add a signal in `signals.py`:

```python
# In prep_reports/signals.py — add after existing signal:
from results.models import MotorAbilityScore  # adjust import

@receiver(post_save, sender=PrepDomainRating)
def sync_motor_ability_score(sender, instance, **kwargs):
    if instance.domain == 'psychomotor':
        MotorAbilityScore.objects.update_or_create(
            student=instance.report_card.student,
            # add your period / term FK here
            trait=instance.trait_name,
            defaults={'score': instance.rating_text},
        )
```

Adjust field names to match your actual `MotorAbilityScore` schema.

---

## 11. Troubleshooting

| Problem | Solution |
|---|---|
| No subjects showing in edit view | Add PrepSubjectSkills for each subject + link subjects to the Standard |
| "No default rating scale" error | In Admin, set `is_default=True` on a RatingScale |
| Teacher sees no classes | Ensure Teacher.assigned_classes includes the Standard of the PrepClass |
| Domain ratings not showing | Add PrepDomainTraitTemplates for the PrepClass (or global) |
| PDF blank | Check WeasyPrint installation; check context processor for school name |
| Bulk create creates 0 records | Ensure students have `current_class` pointing to the Standard of the PrepClass and `is_active=True` |

---

## 12. URL Reference

| URL | Name | Description |
|---|---|---|
| `/prep-reports/` | `prep_reports:dashboard` | Teacher/admin dashboard |
| `/prep-reports/select/` | `prep_reports:select_period` | Period selector |
| `/prep-reports/class/<id>/period/<id>/` | `prep_reports:class_students` | Class student list |
| `/prep-reports/class/<id>/period/<id>/bulk-create/` | `prep_reports:bulk_create` | Bulk create (POST, admin) |
| `/prep-reports/report/<id>/edit/` | `prep_reports:report_card_edit` | Edit report card |
| `/prep-reports/report/<id>/preview/` | `prep_reports:report_card_preview` | Read-only preview |
| `/prep-reports/report/<id>/pdf/` | `prep_reports:report_card_pdf` | PDF download |
| `/prep-reports/admin/classes/` | `prep_reports:admin_class_list` | Admin class management |
