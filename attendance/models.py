from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from students.models import Student
from datetime import date
from django.utils import timezone



class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    present = models.BooleanField(default=False)
    # Add other attendance-specific fields if needed (e.g., status: 'P', 'A', 'L')

    class Meta:
        # Ensures that a student can only have one attendance record per day
        unique_together = ('student', 'date')
        ordering = ['-date', 'student__first_name'] # Order by date (desc) and student name

    def __str__(self):
        return f"{self.student.first_name} - {self.date} - {'Present' if self.present else 'Absent'}"
