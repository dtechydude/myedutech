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

# Subject For E-Learning
class ELearningSubject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='subjects')
    # image = models.ImageField(upload_to=save_subject_image, blank=True, verbose_name='Subject Image')
    description = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return f'{self.name} - {self.standard.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.subject_id)
        super().save(*args, **kwargs)

    class Meta:
      verbose_name = 'E-Learning Subjects'
      verbose_name_plural = 'E-Learning Subjects'
      ordering = ['name']
      unique_together = ('name', 'standard')


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
    

class Lesson(models.Model):
    lesson_id = models.CharField(max_length=100, unique=True)
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE)
    subject = models.ForeignKey(ELearningSubject, on_delete=models.CASCADE, related_name='lessons')
    name = models.CharField(max_length=250, verbose_name="Topic", help_text="Enter the lesson topic (e.g. Heat Energy, Algebraic Expressions)")
    position = models.PositiveSmallIntegerField(verbose_name="Chapter no.")
    video = EmbedVideoField(blank=True, null=True)
    notes = models.FileField(upload_to='save_lesson_files', verbose_name="Notes", blank=True)
    # comment = RichTextField(blank=True, null=True)
    comment = HTMLField(blank=True, null=True)
    # comment = CKEditor5Field('Text', config_name='extends')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        ordering = ['position']
        verbose_name = 'E-Learning Lessons'
        verbose_name_plural = 'E-Learning Lessons'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('curriculum:lesson_list', kwargs={'slug':self.subject.slug, 'standard':self.standard.slug})

    @property
    def html_stripped(self):
       
       return strip_tags(self.comment)
            
            

# comment module
class Comment(models.Model):
    lesson_name = models.ForeignKey(Lesson, null=True, on_delete=models.CASCADE, related_name='comments')
    comm_name = models. CharField(max_length=100, blank=True)
    # reply = models.ForeignKey("comment", null=True, blank=True, on_delete=CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=500)
    date_added = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.comm_name = slugify("comment by" + "-" + str(self.author) + str(self.date_added))
        super().save(*args, **kwargs)

    def __str__(self):
        return self.comm_name

    class Meta:
        ordering = ['-date_added']


class Reply(models.Model):
    comment_name = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='replies')
    reply_body = models.TextField(max_length=500)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "reply to" + str(self.comment_name.comm_name)
    
