from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from users.utils import generate_ref_code


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics', verbose_name='Profile Pic')
    phone = models.CharField(max_length=11, blank=True)

    select = 'Select'
    abia = 'Abia'
    adamawa = 'Adamawa'
    akwa_ibom = 'Akwa_Ibom'
    anambra = 'Anambra'
    bauchi = 'Bauchi'
    bayelsa = 'Bayelsa'
    benue = 'Benue'
    borno = 'Borno'
    cross_river = 'Cross_river'
    delta = 'Delta'
    ebonyi = 'Ebonyi'
    edo = 'Edo'
    ekiti = 'Ekiti'
    enugu = 'Enugu'
    fct_abuja = 'Fct_abuja'
    gombe = 'Gombe'
    imo = 'Imo'
    jigawa = 'Jigawa'
    kaduna = 'Kaduna'
    kano = 'Kano'
    katsina = 'Katsina'
    kebbi = 'Kebbi'
    kogi = 'Kogi'
    kwara = 'Kwara'
    lagos = 'Lagos'
    nasarawa = 'Nasarawa'
    niger = 'Niger'
    ogun = 'Ogun'
    ondo = 'Ondo'
    osun = 'Osun'
    oyo = 'Oyo'
    plateau = 'Plateau'
    rivers = 'Rivers'
    sokoto = 'Sokoto'
    taraba = 'Taraba'
    yobe = 'Yobe'
    zamfara = 'Zamfara'
    
    states = [
        ('Select', select),
        ('Abia', abia),
        ('Adamawa', adamawa),
        ('Akwa_ibom', akwa_ibom),
        ('Anambra', anambra),
        ('Bauchi', bauchi),
        ('Bayelsa', bayelsa),
        ('Benue', benue),
        ('Borno', borno),
        ('Cross_river', cross_river),
        ('Delta', delta),
        ('Ebonyi', ebonyi),
        ('Edo', edo),
        ('Ekiti', ekiti),
        ('Enugu', enugu),
        ('Fct_abuja', fct_abuja),
        ('Gombe', gombe),
        ('Imo', imo),
        ('Jigawa', jigawa),
        ('Kaduna', kaduna),
        ('Katsina', katsina),
        ('Kebbi', kebbi),
        ('Kogi', kogi),
        ('Kwara', kwara),
        ('Lagos', lagos),
        ('Nasarawa', nasarawa),
        ('Niger', niger),
        ('Ogun', ogun),
        ('Ondo', ondo),
        ('Osun', osun),
        ('Oyo', oyo),
        ('Plateau', plateau),
        ('Rivers', rivers),
        ('Sokoto', sokoto),
        ('Taraba', taraba),
        ('Yobe', yobe),
        ('Zamfara', zamfara),
        
    ]
    state_of_origin = models.CharField(max_length=15, choices=states, default=select)
    address = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(max_length=150, blank=True)

    select = 'select'
    teacher = 'teacher'
    student = 'student'
    admin = 'admin'   
    other_staff = 'other_staff'    
    parent = 'parent'  
       
 

    user_types = [
        (select, 'select'),
        (student, 'student'),
        (teacher, 'teacher'),
        (admin, 'admin'),
        (other_staff, 'other_staff'),        
        (parent, 'parent'),                   
             
    ]

    user_type = models.CharField(max_length=20, choices=user_types, default=select, blank=True, null=True)
    code = models.CharField(max_length=6, blank=True) 
    recommended_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,  related_name='ref_by' )
    activate = models.BooleanField(default=False, blank=True, verbose_name='active')   
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    
   
    class Meta:
        ordering = ['user']

#this function returns the profile name in the admin panel profile table
    def __str__ (self):
        return f'username:- {self.user.username} - {self.code}'
    
    def get_recommended_profiles(self):
        qs = Profile.objects.all()
        # my_recs = [p for p in qs if p.recommended_by == self.user]
        my_recs = []
        for profile in qs:
            if profile.recommended_by == self.user:
                my_recs.append(profile)
        return my_recs


    
    def save(self, *args, **kwargs):
        if self.code =="":
            code = generate_ref_code()
            self.code = code
        super().save(*args, **kwargs)
    