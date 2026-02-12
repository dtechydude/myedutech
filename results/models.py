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
    

    

# Work on 002
class Score(models.Model):
    """Represents a student's score in a specific subject for a given term."""
    # ... (Fields remain the same)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    ca1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    ca2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    ca3 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(60)])
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        unique_together = ('student', 'subject', 'term')
        ordering = ['student__first_name', 'student__last_name']
        verbose_name = 'Exams & CA Scores'
        verbose_name_plural = 'Exams & CA Scores'

    def __str__(self):
        return f"{self.student.first_name} - {self.subject.name} ({self.term.name})"

    def clean(self):
        super().clean()
        total_ca = (self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0)
        if total_ca > 40:
            raise ValidationError('The total sum of CA scores (CA1, CA2, CA3) cannot exceed 40.')

    def save(self, *args, **kwargs):
        self.full_clean()

        # --- CORRECTION: Check if ALL score fields are empty/None ---
        # If all fields are None/empty, delete the instance if it exists, and skip creation.
        has_ca_score = any(s is not None for s in [self.ca1, self.ca2, self.ca3])
        has_exam_score = self.exam_score is not None

        if not has_ca_score and not has_exam_score:
            if self.pk:  # Check if the object already exists
                self.delete() # Delete the object instead of saving empty data
            return # Stop the save process

        # Auto-calculate total_score ONLY if some scores are present
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
        verbose_name = "Result Publication Status"
        verbose_name_plural = 'Result Publication Status'
        
    def __str__(self):
        status = 'ALLOWED' if self.is_published else 'BLOCKED'
        return f"{self.student.get_full_name()} ({self.term.name}): {status}"



# MID TERM Results
class MidTermScore(models.Model):
    """
    Represents a student's score for a Mid-Term Exam (Total out of 100), 
    completely independent of Continuous Assessment (CA).
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='midterm_scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    
    # Single field for the Mid-Term Score, out of 100.
    exam_total_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Mid-Term Score (out of 100)"
    )

    class Meta:
        # Each student can only have one mid-term score entry per subject per term
        unique_together = ('student', 'subject', 'term')
        ordering = ['student__last_name', 'subject__name']
        verbose_name = 'Mid-Term Score'
        verbose_name_plural = 'Mid-Term Scores'

    def __str__(self):
        return f"{self.student.first_name} - {self.subject.name} (Mid-Term {self.term.name})"
    
    # Note: No custom save or clean logic needed as it's a single score with built-in validators.
    # The total score is the exam_total_score itself.


class SessionResultStatus(models.Model):
    # Changed 'on_submit' to 'on_delete'
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    session = models.ForeignKey('curriculum.Session', on_delete=models.CASCADE)
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'session')
        verbose_name_plural = "Session Result Status"

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.session.name} - Published: {self.is_published}"