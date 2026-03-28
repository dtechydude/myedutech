from django.db import models
import math
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.db.models.signals import post_save, post_delete
from datetime import timedelta
from django.urls import reverse
from curriculum.models import Standard, Subject, ClassGroup, Session
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
    desc = models.CharField(max_length=50, blank=True, verbose_name='description')
    slug = models.SlugField(null=True, blank=True)
    
    def __str__ (self):
        return f'{self.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    class Meta:       
        verbose_name = 'Prefect Badge'
        verbose_name_plural = 'Prefect Badge'



class Hostel(models.Model):
    name = models.CharField(max_length=50, blank=True, null=True)
    hostel_master = models.ForeignKey(Teacher, on_delete=models.CASCADE, blank=True, null=True, help_text='select hostel master')    
    desc = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(null=True, blank=True)
    
    def __str__ (self):
        return f'{self.name}'

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

#parent Model
class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, help_text='The user account for this parent.')
    guardian_name = models.CharField(max_length=60, blank=False, null=True)  
    guardian_address = models.CharField(max_length=200, blank=True, null=True)  
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)
    guardian_email = models.CharField(max_length=30, blank=True, null=True)
    # You can add other parent-specific fields here if needed,
    # e.g., address, phone_number, etc.
    # The guardian_name, guardian_address, etc., from the Student model
    # can be moved here to avoid redundancy.

    def __str__(self):
        return self.user.get_full_name()


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, help_text='select user or add a new user')    
    USN = models.CharField(max_length=100, help_text='Unique Student Number, Must be same as username')
    first_name = models.CharField(max_length=20)
    middle_name = models.CharField(max_length=20, blank=True, null=True)
    last_name = models.CharField(max_length=20)    
    current_class = models.ForeignKey(Standard, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='classes')
    form_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, blank=True, null=True, related_name='teacher', help_text='This field will be automatically updated when form teacher is set in the standard')
    badge =  models.ForeignKey(Badge, on_delete=models.SET_NULL, blank=True, null=True, related_name='prefect', verbose_name='Prefect')
    
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
    hostel_name = models.ForeignKey(Hostel, on_delete=models.SET_NULL, blank=True, null=True, related_name='hostel_name', verbose_name='hostel')
    date_admitted = models.DateField(default='2020-01-01')
    class_on_admission = models.ForeignKey(Standard, on_delete=models.SET_NULL, blank=True, null=True, related_name='class_on_admission', verbose_name='class_on_admission')
     # Guardian details here..
    parent = models.ForeignKey(Parent, on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    guardian_name = models.CharField(max_length=60, blank=False, null=True)  
    guardian_address = models.CharField(max_length=200, blank=True, null=True)  
    guardian_phone = models.CharField(max_length=15, blank=True, null=True)
    guardian_email = models.CharField(max_length=30, blank=True, null=True)

    select = 'select'
    parent_relationship_choice = 'parent'
    father = 'father'   
    mother = 'mother'
    sister = 'sister'
    brother = 'brother'
    aunt = 'aunt'
    uncle = 'uncle'
    other = 'other'
    

    relationship = [
        (select, 'select'),
        (parent_relationship_choice, 'parent'), # Updated the relationship choices
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
    graduated_session = models.ForeignKey(Session, on_delete=models.SET_NULL, null=True, blank=True, related_name="graduated_students", help_text='only applicable for graduated students')
    fee_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)


    # def __str__(self):
    #     return f'{self.first_name} - {self.last_name}'
    
    # def get_full_name(self):
    #     return f"{self.last_name} {self.first_name} {self.middle_name}"

    def get_full_name(self):
    # Filter out None, empty strings, or whitespace-only strings
        names = [self.last_name, self.first_name, self.middle_name]
        full_name = " ".join(filter(None, names))
        return full_name.strip()
    
    def __str__(self):
        return self.get_full_name()
    
    def get_absolute_url(self):
        return reverse('students:student-detail', kwargs={'id':self.USN})    

    
    class Meta:
        verbose_name = 'Student Details'
        verbose_name_plural = 'Student Details'
        ordering = ['last_name']

    @property
    def get_form_teacher(self):
        """
        Returns the form teacher from the assigned ClassGroup.
        """
        return self.form_teacher if self.current_class else None


class GraduationRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="graduation_records")
    session = models.ForeignKey("curriculum.Session", on_delete=models.SET_NULL, null=True, blank=True)
    graduated_class = models.ForeignKey(Standard, on_delete=models.SET_NULL, null=True, blank=True)
    date_graduated = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.first_name} - {self.session}"   
