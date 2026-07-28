from django.db import models
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.template.defaultfilters import slugify
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.urls import reverse
import os
from django.db.models import Q
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Field
from embed_video.fields import EmbedVideoField
from django.core.exceptions import ValidationError
from djrichtextfield.models import RichTextField
# from portal.models import Dept

from tinymce.models import HTMLField
# from portal.models import Dept
# from staff.models import Teacher



# New School Identity
class SchoolIdentity(models.Model):
    name = models.CharField(max_length=50)
    identity_label = models.CharField(max_length=50, help_text="e.g. Primary, Secondary, or Main", blank=True, null=True)
    is_default = models.BooleanField(default=False, help_text="Fallback identity if no specific class identity is set.")
    # ... (your existing address, phone, logo, signature fields) ...
    address_line_1 = models.CharField(max_length=60)
    address_line_2 = models.CharField(max_length=60, blank=True, null=True)
    phone1 = models.CharField(max_length=11)
    phone2 = models.CharField(max_length=11, blank=True, null=True)
    email = models.CharField(max_length=50, blank=True, null=True)
    website = models.CharField(max_length=50, blank=True, null=True)
    logo = models.ImageField(default='school_logo.jpg', upload_to='official_pics', help_text='must not exceed 180px by 180px in size')
    signature = models.ImageField(blank=True, null=True, upload_to='official_pics', help_text='must not exceed 180px by 180px in size')

    slug = models.SlugField(null=True, blank=True)


    def save(self, *args, **kwargs):
        # Limit to 3 entries
        if not self.pk and SchoolIdentity.objects.count() >= 3:
            raise ValidationError("Kwikschools Portal only supports up to 3 School Identities.")
        
        # Ensure only one is the default
        if self.is_default:
            SchoolIdentity.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
            
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "School Identity Setting"
        verbose_name_plural = "School Identity Settings"

    def __str__(self):
        return f"{self.name} ({self.identity_label})"


# Standard or another branch identity
class StandardIdentity(models.Model):
    # Link to your existing Standard/Class model
    standard = models.OneToOneField('Standard', on_delete=models.CASCADE, related_name='identity_mapping')
    # Link to one of the 3 identities
    school_identity = models.ForeignKey(SchoolIdentity, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Class-Identity Mapping"
        verbose_name_plural = "Class-Identity Mappings"

    def __str__(self):
        return f"{self.standard.name} -> {self.school_identity.identity_label}"


class Session(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField(blank=True, null=True, verbose_name='Start Date')
    end_date = models.DateField(blank=True, null=True, verbose_name='End Date')
    desc = models.TextField(max_length=100, blank=True)

    is_current = models.BooleanField(
        default=False,
        help_text='Check this box if this is the current session'
    )

    slug = models.SlugField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Sessions"
        ordering = ['-start_date']

        # 🔒 Enforce ONLY ONE current session
        constraints = [
            models.UniqueConstraint(
                fields=['is_current'],
                condition=Q(is_current=True),
                name='only_one_current_session'
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 🔥 Auto-unset other current sessions
        if self.is_current:
            Session.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)

        self.slug = slugify(self.name)
        super().save(*args, **kwargs)




class Term(models.Model):
    name = models.CharField(max_length=50)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='terms')
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False, help_text='check the box if the term is current term in the current session')

    class Meta:
        unique_together = ('name', 'session')
        ordering = ['session', 'start_date']
        constraints = [
            models.UniqueConstraint(
                fields=['is_current'],
                condition=Q(is_current=True),
                name='only_one_current_term_can_be_active'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.session.name})"


class PublicHoliday(models.Model):
    """
    A non-schooling day within a specific term (in addition to Saturdays
    and Sundays, which are always excluded automatically). Used to compute
    the actual number of school days open, and to block attendance from
    being taken on that date.
    """
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='public_holidays')
    date = models.DateField()
    description = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = ('term', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.date} - {self.description or 'Public Holiday'} ({self.term.name})"



def save_subject_image(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get file name
    if instance.user.username:
        filename = 'Subject_Pictures/{}.{}'.format(instance.subject_id, ext)
    return os.path.join(upload_to, filename)


class Standard(models.Model):   
    name = models.CharField(max_length=100, unique=True)
    form_teacher = models.ForeignKey(
        'staff.Teacher',  # Use 'app_name.ModelName'
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='form_class'
    )   
    promotion_order = models.IntegerField(unique=True, null=True, blank=True, help_text="Order of classes for promotion (e.g., 0 for the lowest class, 1 for Basic 1, 2 for Basic 2)")
    desc = models.CharField(max_length=200, blank=True, null=True, verbose_name='description') 
    slug = models.SlugField(null=True, blank=True)


    class Meta:
        verbose_name = 'Standard (GRADE LEVELS)'
        verbose_name_plural = 'Standards (GRADE LEVELS)'
        ordering =['promotion_order']

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


def save_lesson_files(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get file name
    if instance.lesson_id:
        filename = 'lesson_files/{}.{}'.format(instance.lesson_id,instance.lesson_id, ext)
        if os.path.exists(filename):
            new_name = str(instance.lesson_id) + str('1')
            filename = 'lesson_images/{}/{}.{}'.format(instance.lesson_id,new_name, ext)
    
    return os.path.join(upload_to, filename)


# NEW CLASSGROUP MODEL
class ClassGroup(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., Creche-Gold, Basic 1-A")
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='groups', default= 1)
    form_teacher = models.ForeignKey('staff.Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='groups')
    
    # New field to define the order of groups within a class for promotion
    # promotion_order = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Class Group'
        verbose_name_plural = 'Class Groups'
        unique_together = ('standard', 'name')
        # ordering = ['standard__promotion_order', 'promotion_order']
        ordering = ['standard']

    def __str__(self):
        return f"{self.standard.name} - {self.name}"



class Subject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100, unique=True)
    # standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='examsubjects', blank=True, null=True)
    # image = models.ImageField(upload_to=save_subject_image, blank=True, verbose_name='Subject Image')
    description = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.subject_id)
        super().save(*args, **kwargs)

    class Meta:
      verbose_name = ' Subjects'
      verbose_name_plural = 'Subjects'
      ordering = ['name']
      


# =====================================================================
# ✅ E-LEARNING MODELS MOVED OUT — now in the independent `elearning` app
# ---------------------------------------------------------------------
# ELearningSubject, Lesson, Comment, Reply (and the unused
# save_lesson_files helper) now live in the standalone `elearning` app —
# see elearning/models.py. There is intentionally NO re-export here:
# elearning is fully independent, so curriculum has no knowledge of it.
#
# If anything elsewhere in your project still does
# `from curriculum.models import Lesson` (or ELearningSubject/Comment/
# Reply/save_lesson_files), update it to `from elearning.models import ...`
# — see the README for a grep command to find every call site.
#
# See curriculum/migrations/0003_move_elearning_models_out.py and
# elearning/migrations/0001_initial.py before running `migrate`.
# =====================================================================


