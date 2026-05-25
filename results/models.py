from django.db import models
from django.contrib.auth.models import User
from users.models import Profile
from students.models import Student
from curriculum.models import Standard, Term, Subject, Session
from django.conf import settings
from django.template.defaultfilters import slugify
from django.core.validators import MaxValueValidator, MinValueValidator 
from django.urls import reverse, reverse_lazy
from django.db import models
from django.db.models import UniqueConstraint, Sum, Avg # Import Avg for average calculations
from django.core.exceptions import ValidationError



class Examination(models.Model):
    name = models.CharField(max_length=150, blank=True)
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, blank=True, null=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='exams') # Link to Term  
    session = models.ForeignKey(Session, on_delete=models.CASCADE) 
  
    date = models.DateField(null=True) 
    description = models.CharField(max_length=150, blank=True)  

    def __str__ (self):
        return f'{self.name} - {self.standard.name} - {self.term}'
    
    class Meta:
        verbose_name = 'Examinations'
        verbose_name_plural = 'Examinations'
        unique_together = ('name', 'term', 'date')
        ordering = ['term__start_date', 'date', 'name']
    


 # School Year Setting for setting the exam scores for CA and Exam
 
class SchoolYearSettings(models.Model):
    """Stores global settings for the school's grading system."""
    max_ca_total = models.DecimalField(
        max_digits=5, decimal_places=2, default=40, 
        help_text="Total maximum allowed for all CA components combined."
    )
    max_exam_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=60,
        help_text="Maximum allowed score for the examination."
    )
    is_active = models.BooleanField(default=True, help_text="Only one setting should be active.")

    class Meta:
        verbose_name = "Grading Configuration"
        verbose_name_plural = "Grading Configurations"

    def __str__(self):
        return f"Grading: CA({self.max_ca_total}) + Exam({self.max_exam_score})"

    def clean(self):
        if (self.max_ca_total + self.max_exam_score) != 100:
            raise ValidationError("The sum of Max CA and Max Exam must equal 100.")
     

# New logic to ensure dynamic input into the score
class Score(models.Model):
    """Represents a student's score in a specific subject for a given term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    
    # We use MinValueValidator(0) but remove hardcoded MaxValueValidators 
    # to allow the dynamic SchoolYearSettings to control the limits via clean()
    ca1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    ca2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    ca3 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        unique_together = ('student', 'subject', 'term')
        ordering = ['student__last_name', 'student__first_name']
        verbose_name = 'Exams & CA Scores'
        verbose_name_plural = 'Exams & CA Scores'

    def __str__(self):
        return f"{self.student.first_name} - {self.subject.name} ({self.term.name})"

    def get_grading_configs(self):
        """Fetches dynamic totals from settings or falls back to defaults."""
        try:
            # Assumes SchoolYearSettings model exists as created in previous step
            from .models import SchoolYearSettings 
            config = SchoolYearSettings.objects.filter(is_active=True).first()
            if config:
                return config.max_ca_total, config.max_exam_score
        except Exception:
            pass
        return 40, 60  # Default fallback if no config is found

    def clean(self):
        super().clean()
        max_ca, max_exam = self.get_grading_configs()
        
        # Calculate totals for validation
        total_ca = (self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0)
        
        # 1. Check total CA against dynamic limit
        if total_ca > max_ca:
            raise ValidationError(f'The total sum of CA scores (CA1, CA2, CA3) cannot exceed {max_ca}.')
        
        # 2. Check Exam Score against dynamic limit
        if self.exam_score is not None and self.exam_score > max_exam:
            raise ValidationError(f'The exam score cannot exceed {max_exam}.')

    def save(self, *args, **kwargs):
        # This triggers the clean() method above
        self.full_clean()

        # Check if ALL score fields are empty/None
        has_ca_score = any(s is not None for s in [self.ca1, self.ca2, self.ca3])
        has_exam_score = self.exam_score is not None

        # If all fields are None/empty, delete the instance if it exists, and skip creation.
        if not has_ca_score and not has_exam_score:
            if self.pk:  
                self.delete() 
            return 

        # Auto-calculate total_score
        total_ca = (self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0)
        
        if self.exam_score is not None:
            self.total_score = total_ca + self.exam_score
        else:
            self.total_score = total_ca 

        super().save(*args, **kwargs)


class MotorAbilityScore(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='motor_ability_scores')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='motor_ability_scores')
    
    # Behavioral Traits (typically 1-5 scale)
    honesty = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Honesty (1=Poor, 5=Excellent)", blank=True, null=True
    )
    politeness = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Politeness (1=Poor, 5=Excellent)", blank=True, null=True
    )
    neatness = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Neatness (1=Poor, 5=Excellent)", blank=True, null=True
    )
    cooperation = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Cooperation (1=Poor, 5=Excellent)", blank=True, null=True
    )
    obedience = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Obedience (1=Poor, 5=Excellent)", blank=True, null=True
    )
    attentiveness = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Attentiveness (1=Poor, 5=Excellent)", blank=True, null=True
    )
    punctuality = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Punctuality (1=Poor, 5=Excellent)", blank=True, null=True
    )
    perseverance = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Perseverance (1=Poor, 5=Excellent)", blank=True, null=True
    )
    emotional_stability = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Emotional Stability (1=Poor, 5=Excellent)", blank=True, null=True
    )
    attitude = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Attitude (1=Poor, 5=Excellent)", blank=True, null=True
    )
    leadership = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Leadership (1=Poor, 5=Excellent)", blank=True, null=True
    )

    # Motor Abilities (typically 1-5 scale)
    physical_education = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Physical Education (1=Poor, 5=Excellent)", blank=True, null=True
    )
    musical = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Musical (1=Poor, 5=Excellent)", blank=True, null=True
    )
    games = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Games (1=Poor, 5=Excellent)", blank=True, null=True
    )
    handwriting = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Handwriting (1=Poor, 5=Excellent)", blank=True, null=True
    )
    reading = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Reading (1=Poor, 5=Excellent)", blank=True, null=True
    )
    verbal_fluency = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Berbal Fluency (1=Poor, 5=Excellent)", blank=True, null=True
    )
    handling_tools = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Score for Handling Tools (1=Poor, 5=Excellent)", blank=True, null=True
    )
    

    date_recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'term') # A student can only have one motor ability score per term
        verbose_name = "Motor Ability Score"
        verbose_name_plural = "Motor Ability Scores"

    def __str__(self):
        return f"{self.student.last_name}'s Motor Ability for {self.term.name}"

    @property
    def get_average_behavioral_score(self):
        scores = [self.honesty, self.politeness, self.neatness, self.cooperation, self.obedience, self.punctuality]
        return sum(scores) / len(scores) if scores else 0

    @property
    def get_average_motor_score(self):
        scores = [self.physical_education, self.games]
        return sum(scores) / len(scores) if scores else 0

    @property
    def get_overall_average_score(self):
        all_scores = [
            self.honesty, self.politeness, self.neatness, self.cooperation,
            self.obedience, self.punctuality, self.physical_education, self.games
        ]
        return sum(all_scores) / len(all_scores) if all_scores else 0
    

# Result Publication Model
class ResultPublication(models.Model):
    """Admin-controlled permission to view a specific student's report for a term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False, verbose_name="Permission Granted to View Report")
    
    class Meta:
        unique_together = ('student', 'term')
        verbose_name = "Result Publication (Termly)"
        verbose_name_plural = 'Result Publication (Termly)'
        
    def __str__(self):
        status = 'ALLOWED' if self.is_published else 'BLOCKED'
        return f"{self.student.get_full_name()} ({self.term.name}): {status}"



# Exam Score Setting
class ExamSetting(models.Model):
    MIDTERM = "Midterm"
    FINAL = "Final"

    EXAM_TYPES = [
        (MIDTERM, "Midterm"),
        (FINAL, "Final"),
    ]

    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    exam_type = models.CharField(max_length=50, choices=EXAM_TYPES)
    max_score = models.PositiveIntegerField()

    class Meta:
        unique_together = ('term', 'exam_type')

    def __str__(self):
        return f"{self.exam_type} - {self.term.name}"
    
    class Meta:
        verbose_name = "Mid-Term Score Setting"
        verbose_name_plural = 'Mid-Term Score Settings'



# # New Mid Term Score

# class MidTermScore(models.Model):
#     student = models.ForeignKey(Student, on_delete=models.CASCADE)
#     subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
#     term = models.ForeignKey(Term, on_delete=models.CASCADE)

#     exam_total_score = models.FloatField(null=True, blank=True)

#     def percentage(self):
#         setting = ExamSetting.objects.get(
#             term=self.term,
#             exam_type="Midterm"
#         )
#         return (self.exam_total_score / setting.max_score) * 100

    
#     class Meta:
#         # Each student can only have one mid-term score entry per subject per term
#         unique_together = ('student', 'subject', 'term')
#         ordering = ['student__last_name', 'subject__name']
#         verbose_name = 'Mid-Term Score'
#         verbose_name_plural = 'Mid-Term Scores'

#     def __str__(self):
#         return f"{self.student.first_name} - {self.subject.name} (Mid-Term {self.term.name})"
 

# New addition for midterm scores

class MidTermScore(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    exam_total_score = models.FloatField(null=True, blank=True, default=0)

    def calculate_total_score(self):
        return self.component_scores.aggregate(
            total=models.Sum('score')
        )['total'] or 0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        total = self.calculate_total_score()

        if self.exam_total_score != total:
            self.exam_total_score = total

            super().save(update_fields=['exam_total_score'])

    def percentage(self):
        setting = ExamSetting.objects.get(
            term=self.term,
            exam_type="Midterm"
        )

        if setting.max_score > 0:
            return (
                self.exam_total_score / setting.max_score
            ) * 100

        return 0

    class Meta:
        unique_together = ('student', 'subject', 'term')
        ordering = ['student__last_name', 'subject__name']
        verbose_name = 'Mid-Term Score'
        verbose_name_plural = 'Mid-Term Scores'

    def __str__(self):
        return (
            f"{self.student.first_name} - "
            f"{self.subject.name} "
            f"(Mid-Term {self.term.name})"
        )

#New Logic For midterm score setting
from django.db import models
from django.core.exceptions import ValidationError


class MidTermComponent(models.Model):
    term = models.ForeignKey(Term, on_delete=models.CASCADE)

    title = models.CharField(max_length=100)

    max_score = models.PositiveIntegerField()

    order = models.PositiveIntegerField(default=1)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']
        unique_together = ('term', 'title')

    def __str__(self):
        return f"{self.title} ({self.max_score})"

    def clean(self):
        """
        Ensure total component scores do not exceed
        ExamSetting maximum score.
        """

        setting = ExamSetting.objects.filter(
            term=self.term,
            exam_type="Midterm"
        ).first()

        if not setting:
            return

        existing_total = MidTermComponent.objects.filter(
            term=self.term
        ).exclude(pk=self.pk).aggregate(
            total=models.Sum('max_score')
        )['total'] or 0

        final_total = existing_total + self.max_score

        if final_total > setting.max_score:
            raise ValidationError(
                f"Total component scores ({final_total}) "
                f"cannot exceed Midterm setting score "
                f"({setting.max_score})."
            )
        
class MidTermComponentScore(models.Model):
    midterm_score = models.ForeignKey(
        MidTermScore,
        on_delete=models.CASCADE,
        related_name='component_scores'
    )

    component = models.ForeignKey(
        MidTermComponent,
        on_delete=models.CASCADE
    )

    score = models.FloatField(default=0)

    class Meta:
        unique_together = ('midterm_score', 'component')

    def __str__(self):
        return (
            f"{self.midterm_score.student} - "
            f"{self.component.title}: {self.score}"
        )

    def clean(self):
        """
        Prevent score from exceeding component maximum.
        """

        if self.score > self.component.max_score:
            raise ValidationError({
                'score': (
                    f"Score cannot exceed "
                    f"{self.component.max_score}"
                )
            })
        
# ============================================
# MIDTERM REPORT REMARK MODEL
# ============================================

class MidTermReportRemark(models.Model):

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE
    )

    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE
    )

    teacher_remark = models.TextField(
        blank=True,
        null=True
    )

    head_teacher_remark = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        unique_together = (
            'student',
            'term',
        )

        ordering = [
            'student__last_name'
        ]

        verbose_name = (
            'Midterm Report Remark'
        )

        verbose_name_plural = (
            'Midterm Report Remarks'
        )

    def __str__(self):

        return (
            f"{self.student} - "
            f"{self.term}"
        )
    


class SessionResultStatus(models.Model):
    # Changed 'on_submit' to 'on_delete'
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    session = models.ForeignKey('curriculum.Session', on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'session')
        verbose_name = "Result Publication (Session)"
        verbose_name_plural = "Result Publication (Session)"

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.session.name} - Published: {self.is_published}"
    


# MODELS FOR TOGGLING CLASS POSITION AND AUTO/MANUAL COMMENT

class ClassPositionSetting(models.Model):
    """
    Settings to toggle whether class position is shown for a given standard/term/session.
    """
    standard = models.ForeignKey(
        Standard,
        on_delete=models.CASCADE,
        related_name='position_settings'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='position_settings'
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='position_settings'
    )
    show_class_position = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('standard', 'term', 'session')
        verbose_name = "Class Position Setting"
        verbose_name_plural = "Class Position Settings"

    def __str__(self):
        status = "Visible" if self.show_class_position else "Hidden"
        return f"{self.standard.name} - {self.term.name} - {self.session.name} ({status})"


class ReportComments(models.Model):
    """
    Stores teacher and principal comments for a specific student's report card.
    Manual entry per student per term and session.
    """
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='report_comments'
    )
    standard = models.ForeignKey(
        Standard,
        on_delete=models.CASCADE,
        related_name='report_comments'
    )
    term = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name='report_comments'
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name='report_comments'
    )
    teacher_comment = models.TextField(blank=True, null=True)
    principal_comment = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_report_comments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'standard', 'term', 'session')
        verbose_name = "Custom Report Comment"
        verbose_name_plural = "Custom Report Comments"

    def __str__(self):
        return f"Comments for {self.student.get_full_name()} - {self.term.name} - {self.session.name}"
