from django.db import models
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.urls import reverse
import os
from django.utils.html import strip_tags
from django_ckeditor_5.fields import CKEditor5Field
from embed_video.fields import EmbedVideoField
from django.core.exceptions import ValidationError
from djrichtextfield.models import RichTextField
# from portal.models import Dept

from tinymce.models import HTMLField
# from portal.models import Dept
from staff.models import Teacher


# Register School
class SchoolIdentity(models.Model):
    name = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=60)
    address_line_2 = models.CharField(max_length=60, blank=True, null=True)
    phone1 = models.CharField(max_length=11)
    phone2 = models.CharField(max_length=11, blank=True, null=True)
    email = models.CharField(max_length=50)
    logo = models.ImageField(default='school_logo.jpg', upload_to='official_pics', help_text='must not exceed 180px by 180px in size')
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = 'School Identity'
        verbose_name_plural = "School Identity Settings"

    # code for ensuring that only single entry is made to this model
    def save(self, *args, **kwargs):
        # Check if any other instance of this model already exists
        if SchoolIdentity.objects.exists() and not self.pk:
            # If an instance exists and we are trying to create a *new* one (self.pk is None),
            # raise a ValidationError.
            raise ValidationError("There can be only one %s instance." % self._meta.verbose_name)
        return super().save(*args, **kwargs)
 
        


class Session(models.Model):
    name = models.CharField(max_length=50)
    first_term = 'First Term'
    second_term = 'Second Term'
    third_term = 'Third Term'
    others = 'Others'

    term_status = [
        (first_term, 'First Term'),
        (second_term, 'Second Term'),
        (third_term, 'Third Term'),
        (others, 'Others'),

    ]

    term = models.CharField(max_length=15, choices=term_status, blank=True, null=True, default='First Term')
    start_date = models.DateField(blank=True, null=True, verbose_name='Start Date')
    end_date = models.DateField(blank=True, null=True, verbose_name='End Date')
    desc = models.TextField(max_length=100, blank=True)
    slug = models.SlugField(null=True, blank=True)

    class Meta:
        unique_together = ['name', 'term']

    def __str__(self):
        return f"{self.name} - {self.term}"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ClassGroup(models.Model):
    name = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(null=True, blank=True)
    
    def __str__ (self):
        return f'{self.name}'
    
    class Meta:
        verbose_name_plural = 'Class Group'
        verbose_name_plural = "Class Group"
        
    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)



def save_subject_image(instance, filename):
    upload_to = 'Images/'
    ext = filename.split('.')[-1]
    # get file name
    if instance.user.username:
        filename = 'Subject_Pictures/{}.{}'.format(instance.subject_id, ext)
    return os.path.join(upload_to, filename)

class Standard(models.Model):   
    name = models.CharField(max_length=100)    
    # dept = models.ForeignKey(Dept, on_delete=models.CASCADE, blank=True, null=True)
    teachers = models.ManyToManyField(Teacher, related_name='classrooms')
    slug = models.SlugField(null=True, blank=True)


    class Meta:
        verbose_name = 'Standards'
        verbose_name_plural = 'Standards'

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




class Subject(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='subjects')
    # image = models.ImageField(upload_to=save_subject_image, blank=True, verbose_name='Subject Image')
    description = models.TextField(max_length=500, blank=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.subject_id)
        super().save(*args, **kwargs)

    class Meta:
      verbose_name = 'E-Learning Subjects'
      verbose_name_plural = 'E-Learning Subjects'


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
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='lessons')
    name = models.CharField(max_length=250)
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
    

#