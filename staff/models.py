from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
# from portal.models import Dept
# from curriculum.utils import Subject, Standard, Dept
from django.template.defaultfilters import slugify
from users.models import Dept
from curriculum.models import Subject, Standard
from datetime import datetime
from django.utils import timezone
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime




# Staff Module
class StaffPosition(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True, help_text='Do not enter anything here')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Staff Roles'
        verbose_name_plural = 'Staff Roles'



class TeacherQuerySet(models.QuerySet):
    def current(self):
        """Teachers who still work at the school."""
        return self.filter(active=True)

    def former(self):
        """Teachers who have left (kept for the archive)."""
        return self.filter(active=False)

# Teacher Module
class Teacher(models.Model):
    objects = TeacherQuerySet.as_manager()
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    first_name = models.CharField(max_length=20, blank=True, null=True)
    middle_name = models.CharField(max_length=20, blank=True, null=True)
    last_name = models.CharField(max_length=20, blank=True, null=True)
    dept = models.ForeignKey(Dept, on_delete=models.CASCADE, default=1, related_name='my_dept', blank=True, null=True)
    # class_in_charge = models.ForeignKey(Standard, on_delete=models.CASCADE, blank=True, null=True, related_name='myclasses')
    subjects_taught = models.ManyToManyField(Subject, related_name='teachers')
    standards_assigned = models.ManyToManyField(Standard, blank=True, related_name='teachers')
    female = 'female'
    male = 'male'
    select_gender = 'select_gender'

    gender_type = [
        ('female', female),
        ('male', male),
        ('select_gender', select_gender),
    ]

    gender= models.CharField(max_length=20, choices=gender_type, default= select_gender)
    DOB = models.DateField(default='1998-01-01')
    date_employed = models.DateField(default='1998-01-01')

    married = 'married'
    single = 'single'
    select = 'select'

    marital_status = [
        (married, 'married'),
        (single, 'single'),
        (select, 'select'),
    ]

    marital_status = models.CharField(max_length=15, choices=marital_status, default=select)
    phone_home = models.CharField(max_length=11, null=True, blank=True)

    # Academic information
    qualification = models.CharField(max_length=150, default='OND')
    year = models.DateField(default='1998-01-01')
    institution = models.CharField(max_length=150, blank=True)
    professional_body = models.CharField(max_length=150, blank=True)

    # Guarantor's information
    guarantor_name = models.CharField(max_length=150, blank=True)
    guarantor_phone = models.CharField(max_length=15, blank=True)
    guarantor_address = models.CharField(max_length=150, blank=True)
    guarantor_email = models.CharField(max_length=60, blank=True)

    # next of kin info
    next_of_kin_name = models.CharField(max_length=60, blank=True)
    next_of_kin_address = models.CharField(max_length=150, blank=True)
    next_of_kin_phone = models.CharField(max_length=15, blank=True)

    staff_role = models.ForeignKey(StaffPosition, on_delete=models.CASCADE, default='select', related_name='staff_role', blank=True, null=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    # active = models.BooleanField(default=False, blank=True)
    active = models.BooleanField(default=True, blank=True,
                                help_text='Untick when the teacher has left the school. '
                                'Their portal access is switched off automatically.')
    date_left = models.DateField(null=True, blank=True)
    left_reason = models.CharField(max_length=200, blank=True)


    def __str__(self):
        return f'{self.first_name} - {self.last_name}'

 
    def get_full_name(self):

        names = [self.user.last_name, self.user.first_name, self.middle_name]
        full_name = " ".join(filter(None, names))
        return full_name.strip()

    @property
    def display_name(self):
        """Safe name for lists (works even when the teacher has no linked user)."""
        if self.user_id:
            return self.user.get_full_name() or self.user.get_username()
        return ' '.join(filter(None, [self.first_name, self.last_name])) or f'Teacher #{self.pk}'

    @property
    def years_of_service(self):
        """Years between date_employed and date_left (or today), to one decimal place."""
        if not self.date_employed:
            return None
        end = self.date_left or timezone.localdate()
        return round(max((end - self.date_employed).days, 0) / 365.25, 1)


    class Meta:
        ordering = ['last_name']

        verbose_name = 'Teachers & Staff Details'
        verbose_name_plural = 'Teachers & Staff Details'



# Teachers Attendance

class StaffAttendance(models.Model):

    STATUS_CHOICES = (
        ('present', 'Present'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('half_day', 'Half Day'),
    )

    teacher = models.ForeignKey(
        'Teacher',
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )

    date = models.DateField(
        default=timezone.localdate
    )

    check_in_time = models.TimeField(
        null=True,
        blank=True
    )

    check_out_time = models.TimeField(
        null=True,
        blank=True
    )

    checked_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_checked_in'
    )

    checked_out_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_checked_out'
    )

    is_late = models.BooleanField(
        default=False
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='present'
    )

    remarks = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ('teacher', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.teacher} - {self.date}"

    @property
    def work_duration(self):
        """
        Returns formatted work duration (e.g. 6 hrs 30 mins)
        """

        if self.check_in_time and self.check_out_time:

            start = datetime.combine(
                self.date,
                self.check_in_time
            )

            end = datetime.combine(
                self.date,
                self.check_out_time
            )

            duration = end - start

            total_seconds = duration.total_seconds()

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            return f"{int(hours)} hrs {int(minutes)} mins"

        return "N/A"


class TeacherStatusLog(models.Model):
    """Who marked a teacher as left / reactivated, when, and why."""
    DEACTIVATED = 'deactivated'
    REACTIVATED = 'reactivated'
    ACTIONS = [(DEACTIVATED, 'Marked as left the school'), (REACTIVATED, 'Reactivated')]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='status_logs')
    action = models.CharField(max_length=20, choices=ACTIONS)
    reason = models.CharField(max_length=200, blank=True)
    effective_date = models.DateField(default=timezone.localdate)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='teacher_status_changes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.teacher} - {self.get_action_display()} ({self.effective_date})'


# Automatic access control + audit trail for status changes (see teacher_status.py)
from . import teacher_status  # noqa: E402,F401