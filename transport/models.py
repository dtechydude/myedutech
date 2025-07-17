from django.db import models
from staff.models import Teacher
from students.models import Student
from django.template.defaultfilters import slugify
from django.conf import settings
from django.urls import reverse
from django.core.validators import MinLengthValidator, MaxValueValidator, MinValueValidator 


# Create your models here.


class Route(models.Model):
    route_id = models.CharField(max_length=8,null=True, blank=True, help_text='Could be Bus Number')
    name = models.CharField(max_length=200, blank=True )
    direction = models.CharField(max_length=200, blank=True)
    staff_in_charge = models.ForeignKey(Teacher, on_delete=models.CASCADE, default=None, null=True, related_name='official_staff')
    driver = models.CharField(max_length=200, blank=True, unique=True)
    slug = models.SlugField(null=True, blank=True)

    def __str__ (self):
        return f'{self.name} - {self.route_id}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class StudentOnRoute(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='studentonroute',
                                help_text="The student associated with this route.")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, default= None, related_name='routes') 
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)  
   

    class Meta:
        ordering = ['student' ]

        unique_together = ['student', 'route']
    

    def __str__ (self):
       return f'{self.student}'
