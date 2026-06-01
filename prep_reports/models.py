"""
KwikSchools — Prep/Nursery Report Card Models
=============================================
Handles checklist-style report cards for preparatory classes
(Pre-Nursery, Nursery, KG etc.) where teachers tick skill
achievement columns instead of entering numeric scores.

Integrates with:
  - curriculum.models.Standard  (class / form)
  - curriculum.models.Subject   (subject)
  - students.models.Student     (pupil, linked to auth.User; has USN)
  - results.models.MotorAbilityScore (psychomotor ratings)
  - The default auth.User model for teachers
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

User = get_user_model()


# ---------------------------------------------------------------------------
# 1. Prep Class Configuration
#    Schools flag which Standards use the prep report card system.
# ---------------------------------------------------------------------------

class PrepClass(models.Model):
    """
    Marks a Standard as a 'preparatory' class that uses the
    checklist-based report card instead of the normal numeric system.
    """
    standard = models.OneToOneField(
        'curriculum.Standard',
        on_delete=models.CASCADE,
        related_name='prep_config',
        verbose_name="Class / Standard"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Prep Class Configuration"
        verbose_name_plural = "Prep Class Configurations"
        ordering = ['standard__name']

    def __str__(self):
        return f"Prep Config — {self.standard}"


# ---------------------------------------------------------------------------
# 2. Rating Scale
#    Configurable columns: e.g. A/B/C/D/E  OR  Apprentice/Practitioner/Expert
# ---------------------------------------------------------------------------

class RatingScale(models.Model):
    """
    A named rating scale belonging to a school session or global.
    e.g.  "PurpleStars Scale"  ->  columns: A, B, C, D, E
          "Watford Scale"      ->  columns: Apprentice, Practitioner, Expert
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text="If checked, new prep classes will use this scale."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rating Scale"
        verbose_name_plural = "Rating Scales"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Only one default scale at a time
        if self.is_default:
            RatingScale.objects.exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class RatingColumn(models.Model):
    """
    A single column within a RatingScale.
    order controls the left-to-right display sequence.
    """
    scale = models.ForeignKey(
        RatingScale,
        on_delete=models.CASCADE,
        related_name='columns'
    )
    label = models.CharField(max_length=50, help_text="e.g. A, B, Apprentice, Expert")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Rating Column"
        verbose_name_plural = "Rating Columns"
        ordering = ['scale', 'order']
        unique_together = ('scale', 'label')

    def __str__(self):
        return f"{self.scale.name} → {self.label}"


# ---------------------------------------------------------------------------
# 3. Subject Skill / Learning Objective
#    Each subject has a list of observable skills / competencies.
# ---------------------------------------------------------------------------

class PrepSubjectSkill(models.Model):
    """
    A single checkable skill/competency under a subject for a prep class.
    e.g.  Subject: Numeracy
          Skill:   "The child is able to count 1–100 on the number chart"
    """
    subject = models.ForeignKey(
        'curriculum.Subject',
        on_delete=models.CASCADE,
        related_name='prep_skills'
    )
    # Optionally restrict to specific prep classes
    prep_class = models.ForeignKey(
        PrepClass,
        on_delete=models.CASCADE,
        related_name='skills',
        null=True,
        blank=True,
        help_text="Leave blank to apply to ALL prep classes."
    )
    description = models.TextField(
        help_text="Observable skill / learning objective statement."
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Prep Subject Skill"
        verbose_name_plural = "Prep Subject Skills"
        ordering = ['subject', 'order']

    def __str__(self):
        return f"[{self.subject}] {self.description[:60]}"


# ---------------------------------------------------------------------------
# 4. Academic Period — bridges to curriculum.Session + curriculum.Term
#
#    We do NOT duplicate session/term data.
#    We add only the two fields the prep report card needs that Term lacks:
#      - next_term_begins  (printed on the report card header)
#      - days_school_opened (printed on the report card header)
#
#    is_current is derived from Session.is_current AND Term.is_current
#    so there is zero duplication of the active-flag logic.
# ---------------------------------------------------------------------------

class PrepAcademicPeriod(models.Model):
    """
    One row = one Term within one Session, enriched with the two extra
    fields the prep report card header requires.

    Both FKs point at your existing curriculum records.
    The school creates one PrepAcademicPeriod per term, linking it to
    the curriculum Session and Term they already manage.
    """

    session = models.ForeignKey(
        'curriculum.Session',
        on_delete=models.PROTECT,
        related_name='prep_periods',
        help_text="Academic session — select from Curriculum → Sessions."
    )
    term = models.ForeignKey(
        'curriculum.Term',
        on_delete=models.PROTECT,
        related_name='prep_periods',
        help_text="Term within that session — select from Curriculum → Terms."
    )

    # These two fields do not exist on curriculum.Term,
    # so we own them here for the report card header.
    next_term_begins = models.DateField(
        null=True,
        blank=True,
        help_text="Date printed on report card: 'Next term begins …'"
    )
    days_school_opened = models.PositiveSmallIntegerField(
        default=0,
        help_text="Number of days school opened this term (report card header)."
    )

    class Meta:
        verbose_name = "Prep Academic Period"
        verbose_name_plural = "Prep Academic Periods"
        unique_together = ('session', 'term')
        ordering = ['-session__start_date', 'term__start_date']

    def __str__(self):
        return f"{self.term.name} — {self.session.name}"

    # ------------------------------------------------------------------
    # Proxy properties — keep the rest of the codebase unchanged
    # ------------------------------------------------------------------

    @property
    def session_name(self):
        """e.g. '2024/2025'"""
        return self.session.name

    @property
    def term_name(self):
        """e.g. 'First Term'"""
        return self.term.name

    @property
    def start_date(self):
        return self.term.start_date

    @property
    def end_date(self):
        return self.term.end_date

    @property
    def is_current(self):
        """
        True only when BOTH the linked Session and Term are currently active.
        Reads directly from curriculum's own is_current flags — no duplication.
        """
        return bool(self.session.is_current and self.term.is_current)

    # ------------------------------------------------------------------
    # Class-level helper used by views / services
    # ------------------------------------------------------------------

    @classmethod
    def get_current(cls):
        """
        Returns the PrepAcademicPeriod whose session AND term are both
        currently active, or None.
        Filters on the DB side for efficiency.
        """
        return (
            cls.objects
            .select_related('session', 'term')
            .filter(session__is_current=True, term__is_current=True)
            .first()
        )


# ---------------------------------------------------------------------------
# 5. Prep Report Card (one per student per period)
# ---------------------------------------------------------------------------

class PrepReportCard(models.Model):
    """
    The master report card record for a single pupil in a given period.
    Stores attendance, comments and links to individual skill entries.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('published', 'Published'),
    ]

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='prep_report_cards'
    )
    prep_class = models.ForeignKey(
        PrepClass,
        on_delete=models.CASCADE,
        related_name='report_cards'
    )
    period = models.ForeignKey(
        PrepAcademicPeriod,
        on_delete=models.CASCADE,
        related_name='report_cards'
    )
    rating_scale = models.ForeignKey(
        RatingScale,
        on_delete=models.PROTECT,
        related_name='report_cards'
    )

    # Attendance
    days_present = models.PositiveSmallIntegerField(default=0)
    days_absent = models.PositiveSmallIntegerField(default=0)

    # Promotion
    promoted_to = models.ForeignKey(
        'curriculum.Standard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promoted_prep_students',
        help_text="Class pupil is promoted to (leave blank if not yet decided)."
    )

    # Teacher comments
    class_teacher_comment = models.TextField(blank=True)
    head_teacher_comment = models.TextField(blank=True)

    # Workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_prep_reports'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_prep_reports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prep Report Card"
        verbose_name_plural = "Prep Report Cards"
        unique_together = ('student', 'period', 'prep_class')
        ordering = ['-period__session__start_date', 'period__term__start_date', 'student__user__last_name']

    def __str__(self):
        return (
            f"{self.student} — "
            f"{self.prep_class.standard} — "
            f"{self.period}"
        )

    @property
    def days_school_opened(self):
        return self.period.days_school_opened

    @property
    def student_full_name(self):
        u = self.student.user
        return f"{u.last_name} {u.first_name} {u.student.middle_name}".strip().upper()


# ---------------------------------------------------------------------------
# 6. Skill Score Entry (one per skill per report card)
# ---------------------------------------------------------------------------

class PrepSkillEntry(models.Model):
    """
    Records the teacher's tick for a single skill on a report card.
    Only ONE column can be selected per skill (radio-button behaviour).
    Also stores the teacher's optional comment for this subject/skill group.
    """
    report_card = models.ForeignKey(
        PrepReportCard,
        on_delete=models.CASCADE,
        related_name='skill_entries'
    )
    skill = models.ForeignKey(
        PrepSubjectSkill,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    selected_column = models.ForeignKey(
        RatingColumn,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entries',
        help_text="The column ticked by the teacher (null = not yet rated)."
    )
    # Per-subject teacher comment (stored on first skill of subject per card)
    subject_comment = models.TextField(
        blank=True,
        help_text="Optional teacher comment for this subject."
    )
    entered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='prep_skill_entries'
    )
    entered_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prep Skill Entry"
        verbose_name_plural = "Prep Skill Entries"
        unique_together = ('report_card', 'skill')
        ordering = ['skill__subject', 'skill__order']

    def __str__(self):
        col = self.selected_column.label if self.selected_column else "—"
        return f"{self.report_card.student} | {self.skill} → {col}"


# ---------------------------------------------------------------------------
# 7. Affective / Psychomotor Domain Ratings
#    Linked to the existing MotorAbilityScore model.
#    Form-teacher-only; stored per report card.
# ---------------------------------------------------------------------------

class PrepDomainRating(models.Model):
    """
    Stores numeric or text ratings for affective/psychomotor traits
    per report card.  Complements the existing MotorAbilityScore.

    Trait examples: Punctuality, Neatness, Handwriting, Verbal Fluency…
    Rating can be a number (1–5) or a text label.
    """
    DOMAIN_CHOICES = [
        ('psychomotor', 'Psychomotor Domain'),
        ('affective', 'Affective / Cognitive Domain'),
    ]

    report_card = models.ForeignKey(
        PrepReportCard,
        on_delete=models.CASCADE,
        related_name='domain_ratings'
    )
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES)
    trait_name = models.CharField(max_length=100)
    rating_text = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g. Excellent, Distinction, 4, 5"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Prep Domain Rating"
        verbose_name_plural = "Prep Domain Ratings"
        ordering = ['domain', 'order']
        unique_together = ('report_card', 'domain', 'trait_name')

    def __str__(self):
        return (
            f"{self.report_card.student} | "
            f"{self.trait_name}: {self.rating_text}"
        )


# ---------------------------------------------------------------------------
# 8. Domain Trait Template
#    Reusable trait definitions per prep class so the form auto-populates.
# ---------------------------------------------------------------------------

class PrepDomainTraitTemplate(models.Model):
    """
    Template trait for a given prep class configuration.
    When a new report card is created, these traits are auto-created
    as PrepDomainRating entries (blank) for the teacher to fill.
    """
    prep_class = models.ForeignKey(
        PrepClass,
        on_delete=models.CASCADE,
        related_name='domain_trait_templates',
        null=True,
        blank=True,
        help_text="Leave blank for global (all prep classes)."
    )
    domain = models.CharField(
        max_length=20,
        choices=PrepDomainRating.DOMAIN_CHOICES
    )
    trait_name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Domain Trait Template"
        verbose_name_plural = "Domain Trait Templates"
        ordering = ['domain', 'order']

    def __str__(self):
        return f"{self.domain.upper()} | {self.trait_name}"
