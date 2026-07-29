from django.db import models
from django.contrib.auth.models import User
# Assuming your curriculum app exists for Standard/Session
from curriculum.models import Standard, Session, Subject, Term
# from results.models import Examination
from django.utils import timezone
from datetime import timedelta
import re




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
        verbose_name = 'Examination Settings'
        verbose_name_plural = 'Examination Settings'
        unique_together = ('name', 'term', 'date')
        ordering = ['term__start_date', 'date', 'name']
    



class Quiz(models.Model):
    examination = models.ForeignKey(Examination, on_delete=models.CASCADE, null=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True)
    term = models.CharField(
        max_length=50,
        choices=[('First', 'First'), ('Second', 'Second'), ('Third', 'Third')]
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cbt_session'
    )
    number_of_questions = models.IntegerField(default=0)
    time = models.IntegerField(help_text="Duration in minutes")
    required_score_to_pass = models.IntegerField(help_text="Percentage (e.g., 50)")
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='cbt_exams')
    active = models.BooleanField(default=False)

    # 🔹 NEW FIELDS (availability control)
    start_date = models.DateField(help_text="Date exam becomes available")
    end_date = models.DateField(help_text="Date exam expires")
    start_time = models.TimeField(help_text="Daily opening time")
    end_time = models.TimeField(help_text="Daily closing time")
    # start_date = models.DateField(null=True, blank=True, help_text="Date exam becomes available")
    # end_date = models.DateField(null=True, blank=True, help_text="Date exam expires")
    # start_time = models.TimeField(null=True, blank=True, help_text="Daily opening time")
    # end_time = models.TimeField(null=True, blank=True, help_text="Daily closing time")


    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['examination', 'subject', 'term', 'session'],
                name='unique_quiz_per_exam_context'
            )
        ]
        verbose_name = "CBT Exam"
        verbose_name_plural = "CBT Exams"

    @property
    def exam_name(self):
        return self.examination.name if self.examination else "Unnamed Exam"

    @property
    def subject_name(self):
        return self.subject.name if self.subject else "Unnamed Subject"

    # @property
    # def standard_name(self):
    #     return self.standard.name if self.standard else "Unnamed Standard"

    def __str__(self):
        return f"{self.exam_name} - {self.subject_name} - {self.standard.name}"

    def get_questions(self):
        import random
        qs = list(self.question_set.all())
        random.shuffle(qs)
        return qs[:self.number_of_questions]



class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey('Quiz', on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    # ✅ NEW FIELDS (Safe Cancel System)
    cancelled = models.BooleanField(default=False)
    cancelled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cancelled_attempts'
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def get_time_left(self):
        """Calculates remaining time in seconds"""
        expiry_time = self.start_time + timedelta(minutes=self.quiz.time)
        remaining = expiry_time - timezone.now()
        return max(0, int(remaining.total_seconds()))

    def __str__(self):
        return f"{self.user.username} {self.user.last_name} - {self.quiz}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    content = models.TextField(verbose_name="Question Text")
    
    # New field for Google Drive Links
    image_url = models.URLField(
        blank=True, 
        null=True, 
        help_text="Paste the Google Drive 'Share' link here."
    )
    
    TYPES = [
        ('MCQ', 'Multiple Choice (A, B, C, D)'),
        ('SHORT', 'Short Answer (Fill in)'),
    ]
    question_type = models.CharField(max_length=10, choices=TYPES, default='MCQ')

    option_a = models.CharField(max_length=200, blank=True, null=True)
    option_b = models.CharField(max_length=200, blank=True, null=True)
    option_c = models.CharField(max_length=200, blank=True, null=True)
    option_d = models.CharField(max_length=200, blank=True, null=True)
    
    correct_answer = models.CharField(
        max_length=200, 
        help_text="For MCQ: enter A, B, C, or D. For Short Answer: enter the correct word."
    )

    def __str__(self):
        return f"{self.quiz.exam_name} - {self.quiz.standard.name} - {self.content[:50]}"

    @property
    def direct_image_url(self):
        """
        Converts a standard Google Drive share link into a direct image source URL.
        """
        if not self.image_url:
            return None
        
        # If it's already a direct link, return it
        if "googleusercontent.com" in self.image_url:
            return self.image_url
            
        # Regex to extract the File ID from various Google Drive link formats
        drive_regex = r"(?:/d/|id=)([\w-]+)"
        match = re.search(drive_regex, self.image_url)
        
        if match:
            file_id = match.group(1)
            # Returns the direct thumbnail/view link format
            return f"https://drive.google.com/uc?export=view&id={file_id}"
            
        return self.image_url

    def check_answer(self, student_answer):
        if self.question_type == 'MCQ':
            return student_answer.strip().upper() == self.correct_answer.strip().upper()
        else:
            return student_answer.strip().lower() == self.correct_answer.strip().lower()

    class Meta:
        verbose_name = "CBT Question"
        verbose_name_plural = "CBT Questions"



class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.question.text} - {self.text}"




# class QuizResult(models.Model):
#     quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cbt_results')
#     score = models.FloatField()
#     passed = models.BooleanField(default=False)
#     timestamp = models.DateTimeField(auto_now_add=True)

#     cancelled = models.BooleanField(default=False)  # ✅ NEW FIELD

#     # def __str__(self):
#     #     return f"{self.user} - {self.quiz} ({self.score}%)"
    
#     #     # Before
#     # def __str__(self):
#     #     return f"{self.user} - {self.quiz} ({self.score}%)"

#     # After
#     def __str__(self):
#         return f"{self.user} - {self.quiz} ({self.score:.1f}%)"

class QuizResult(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cbt_results')
    score = models.FloatField()
    passed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    cancelled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} - {self.quiz} ({self.score:.1f}%)"

    # ✅ NEW — computed, not stored. QuizResult only ever saved a
    # percentage, so the raw "X out of Y" count is derived from that
    # percentage against the quiz's question count, the same way
    # attendance_percentage/days_absent are derived elsewhere. Rounds to
    # the nearest whole question since score is a float percentage.
    @property
    def correct_answers_count(self):
        total = self.quiz.number_of_questions or 0
        if total <= 0:
            return None
        return round((self.score / 100) * total)

    @property
    def total_questions(self):
        return self.quiz.number_of_questions