from django.db import models
from django.contrib.auth.models import User
from users.models import Profile
from students.models import Student
from curriculum.models import Standard, Term, Subject
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
    date = models.DateField(null=True) 
    description = models.CharField(max_length=150, blank=True)  

    def __str__ (self):
        return f'{self.name} - {self.date}'
    
    class Meta:
        verbose_name = 'Examinations'
        verbose_name_plural = 'Examinations'
        unique_together = ('name', 'term', 'date')
        ordering = ['term__start_date', 'date', 'name']
    


# class Result(models.Model):
#     student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results') # Added related_name
#     subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
#     exam = models.ForeignKey(Examination, on_delete=models.CASCADE) # Link to the Exam
#     score = models.DecimalField(max_digits=5, decimal_places=2)

#     class Meta:
#         # Ensures that for a given student in a given exam, a subject can only appear once.
#         constraints = [
#             UniqueConstraint(fields=['student', 'subject', 'exam'], name='unique_student_subject_exam_result')
#         ]
#         ordering = ['student', 'exam', 'subject'] # Optional: default ordering

#     def __str__(self):
#         return f"{self.student.first_name}'s {self.subject.name} Score in {self.exam.name}: {self.score}"
    

    
#works well 001
class Score(models.Model):
    """Represents a student's score in a specific subject for a given term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scores')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    # Continuous Assessment (CA) scores - adjust fields as per school's grading system
    ca1 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    ca2 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    ca3 = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(40)])
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(60)])
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        # Each student can only have one score entry per subject per term
        unique_together = ('student', 'subject', 'term')
        ordering = ['student__first_name', 'student__last_name']
        verbose_name = 'Exams & CA Scores'
        verbose_name_plural = 'Exams & CA Scores'

    def __str__(self):
        return f"{self.student.first_name} - {self.subject.name} ({self.term.name})"

    # def save(self, *args, **kwargs):
    #     # Auto-calculate total_score if CA and exam scores are present
    #     total_ca = 0
    #     if self.ca1 is not None:
    #         total_ca += self.ca1
    #     if self.ca2 is not None:
    #         total_ca += self.ca2
    #     if self.ca3 is not None:
    #         total_ca += self.ca3
       
    #     if self.exam_score is not None:
    #         self.total_score = total_ca + self.exam_score
    #     else:
    #         self.total_score = total_ca # If only CA scores are available

    #     super().save(*args, **kwargs)

    def clean(self):
        """
        Custom validation to ensure total CA score does not exceed 40.
        """
        super().clean()
        total_ca = (self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0)
        if total_ca > 40:
            raise ValidationError('The total sum of CA scores (CA1, CA2, CA3) cannot exceed 40.')

    def save(self, *args, **kwargs):
        self.full_clean() # Call full_clean to run the validation check

        # Auto-calculate total_score
        total_ca = (self.ca1 or 0) + (self.ca2 or 0) + (self.ca3 or 0)
        
        if self.exam_score is not None:
            self.total_score = total_ca + self.exam_score
        else:
            self.total_score = total_ca # If only CA scores are available

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