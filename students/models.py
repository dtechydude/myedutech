from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.urls import reverse
from curriculum.models import Standard, Subject, ClassGroup
# from portal.models import Teacher
from staff.models import Teacher
# from attendance.models import AttendanceTotal
from datetime import date



# Blood Group
A_Positive = 'A+'
A_Negative = 'A-'
B_Positive = 'B+'
AB_Positive = 'AB+'
AB_Negative = 'AB-'
O_Positive = 'O+'
O_Negative = 'O-'
select = 'select'


blood_group = [
    (A_Positive, 'A+'),
    (A_Negative, 'B-'),
    (B_Positive, 'B+'),
    (AB_Positive, 'AB+'),
    (AB_Negative, 'AB-'),
    (O_Positive, 'O+'),
    (O_Negative, 'O-'),
    (select, 'select'), 

]

# Genotype
AA = 'AA'
AS = 'AS'
AC = 'AC'
SS = 'SS'
select = 'select'

genotype = [
    (AA, 'AA'),
    (AS, 'AS'),
    (AC, 'AC'),
    (SS, 'SS'),
    (select, 'select'),
    
]


class Badge(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    desc = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(null=True, blank=True)
    
    def __str__ (self):
        return f'{self.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    class Meta:       
        verbose_name = 'Prefect'
        verbose_name_plural = 'Prefects'



class Hostel(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    hostel_master = models.ForeignKey(Teacher, on_delete=models.CASCADE, null=True, help_text='select hostel master')    
    desc = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(null=True, blank=True)
    
    def __str__ (self):
        return f'{self.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, help_text='select user or add a new user')    
    USN = models.CharField(max_length=100, help_text='Unique Student Number, Must be same as username')
    first_name = models.CharField(max_length=20)
    middle_name = models.CharField(max_length=20, blank=True, null=True)
    last_name = models.CharField(max_length=20)    
    current_class = models.ForeignKey(Standard, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')
    form_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, blank=True, null=True, related_name='teacher')
    badge =  models.ForeignKey(Badge, on_delete=models.CASCADE, blank=True, null=True, verbose_name='Prefect')
    
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
    # medical information
    blood_group = models.CharField(max_length=15, choices=blood_group, default=select)
    genotype = models.CharField(max_length=15, choices=genotype, default=select)
    health_remark = models.CharField(max_length=60, blank=False, null=True, default='enter health detail')    

    day_student = 'day_student'
    boarder = 'boarder'

    student_types = [
        (day_student, 'day_student'),
        (boarder, 'boarder'),

    ]

    student_type = models.CharField(max_length=15, choices=student_types, default=day_student)
    hostel_name = models.ForeignKey(Hostel, on_delete=models.CASCADE, blank=True, null=True, related_name='hostel_name', verbose_name='hostel')
    date_admitted = models.DateField(default='2020-01-01')
    class_on_admission = models.ForeignKey(Standard, on_delete=models.CASCADE, blank=True, null=True, related_name='class_on_admission', verbose_name='class_on_admission')
     # Guardian details here..
    guardian_name = models.CharField(max_length=60, blank=False)  
    guardian_address = models.CharField(max_length=200, blank=True)  
    guardian_phone = models.CharField(max_length=15, blank=True)
    guardian_email = models.CharField(max_length=30, blank=True)

    select = 'select'
    parent = 'parent'
    father = 'father'   
    mother = 'mother'
    sister = 'sister'
    brother = 'brother'
    aunt = 'aunt'
    uncle = 'uncle'
    other = 'other'
    

    relationship = [
        (select, 'select'),
        (parent, 'parent'),
        (father, 'father'),
        (mother, 'mother'),
        (sister, 'sister'),
        (brother, 'brother'),
        (aunt, 'aunt'),
        (uncle, 'uncle'),
        (other, 'other'),          

    ]

    relationship = models.CharField(max_length=25, choices=relationship, default=select, help_text="Guardian's Relationship With Student")
    
    active = 'active'
    inactive = 'inactive'
    graduated = 'graduated'
    dropped = 'dropped'
    expelled = 'expelled'
    suspended = 'suspended'

    student_status = [
        (active, 'active'),
        (inactive, 'inactive'),
        (graduated, 'graduated'),
        (dropped, 'dropped'),
        (expelled, 'expelled'),
        (suspended, 'suspended'),

    ]

    student_status = models.CharField(max_length=15, choices=student_status, default=active)

    def __str__(self):
        return f'{self.first_name} - {self.last_name}'
    
    class Meta:
        ordering = ['user']   
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_absolute_url(self):
        return reverse('students:student-detail', kwargs={'id':self.USN})
    
# Student ID Card Generation
class StudentId(models.Model):
    id_card = models.BooleanField( default=False) 
    student = models.ForeignKey(Student, related_name='idcardimage', on_delete=models.CASCADE, blank=True, null=True, default=None,)
    f_1 = models.ImageField(default='school_id_header.jpg', upload_to='school_logo', help_text='Do not upload file')
    f_2 = models.ImageField(default='qr_code.jpg', upload_to='school_logo', help_text='Do not upload file')
    f_3 = models.ImageField(default='sign.jpg', upload_to='school_logo', help_text='Do not upload file')

    def __str__(self):
      return f"IdCard: {self.student}" 

    class Meta:
        verbose_name = 'Confirm to enable student generate ID Card'


