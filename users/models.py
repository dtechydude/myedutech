from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from users.utils import generate_ref_code
import os
from django.core.exceptions import ValidationError




MAX_PROFILE_IMAGE_BYTES = 100 * 1024  # 100 KB — hard cap, enforced everywhere


def validate_image_max_size(file):
    """
    Model-level validator. Runs automatically whenever a ModelForm calls
    full_clean() (this covers Django Admin and any ModelForm-based view).
    It is the single source of truth for the 100KB cap — no upload path
    can bypass it just by not calling a specific service function.
    """
    if file.size > MAX_PROFILE_IMAGE_BYTES:
        raise ValidationError(
            f'Image too large ({file.size / 1024:.1f} KB). Maximum allowed '
            f'size is 100 KB. Please compress the image and try again.'
        )


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(
        default='default.jpg',
        upload_to='profile_pics',
        verbose_name='Profile Pic',
        blank=True,
        null=True,
        validators=[validate_image_max_size],
    )
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
    address = models.CharField(max_length=150, blank=True, null=True)
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
        verbose_name = 'User Profiles'
        verbose_name_plural = 'User Profiles'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_image_name = self.image.name if self.image else None

    def __str__(self):
        return f'username:- {self.user.username} - {self.user.last_name} - {self.user.first_name}'

    def get_recommended_profiles(self):
        qs = Profile.objects.all()
        my_recs = []
        for profile in qs:
            if profile.recommended_by == self.user:
                my_recs.append(profile)
        return my_recs

    def save(self, *args, **kwargs):
        if self.code == "":
            self.code = generate_ref_code()

        # ── Enforce the 100KB cap on EVERY save path, not just forms that
        # call full_clean() (e.g. service code that assigns the field and
        # calls .save() directly, like bulk_photos.py).
        # `_committed` is False when a *new* file has been attached this
        # save cycle — we don't want to re-validate an already-saved file
        # every time an unrelated field changes.
        if self.image and hasattr(self.image, '_committed') and not self.image._committed:
            validate_image_max_size(self.image)

        # ── Auto-delete the previous image file whenever it's being
        # replaced — regardless of which view/service triggered the save.
        if self.pk:
            try:
                old = Profile.objects.only('image').get(pk=self.pk)
                if (
                    old.image
                    and old.image.name != self.image.name
                    and old.image.name != 'default.jpg'
                ):
                    old.image.storage.delete(old.image.name)
            except Profile.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    @property
    def image_url(self):
        if self.image:
            return self.image.url
        return '/static/pages/images/default.jpg'





class Dept(models.Model):
    id = models.CharField(primary_key='True', max_length=100)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'School Departments'
        verbose_name_plural = 'School Departments'

    