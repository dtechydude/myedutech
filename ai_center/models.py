# from django.db import models

# # Create your models here.
# from django.db import models


# class AIToolCategory(models.Model):

#     name = models.CharField(
#         max_length=100,
#         unique=True
#     )

#     icon = models.CharField(
#         max_length=100,
#         blank=True
#     )

#     class Meta:
#         ordering = ['name']

#     def __str__(self):
#         return self.name


# class PromptCategory(models.Model):

#     name = models.CharField(
#         max_length=100,
#         unique=True
#     )

#     slug = models.SlugField(
#         unique=True
#     )

#     display_order = models.PositiveIntegerField(
#         default=0
#     )

#     is_active = models.BooleanField(
#         default=True
#     )

#     class Meta:
#         ordering = ['display_order', 'name']
#         verbose_name = 'Prompt Category'
#         verbose_name_plural = 'Prompt Categories'

#     def __str__(self):
#         return self.name


# class AITool(models.Model):

#     category = models.ForeignKey(
#         AIToolCategory,
#         on_delete=models.CASCADE,
#         related_name='tools'
#     )

#     name = models.CharField(
#         max_length=150
#     )

#     description = models.TextField()

#     best_for = models.TextField(
#         help_text="Comma separated tags"
#     )

#     website_url = models.URLField()

#     icon_class = models.CharField(
#         max_length=100,
#         default='fas fa-robot'
#     )

#     is_featured = models.BooleanField(
#         default=False
#     )

#     is_active = models.BooleanField(
#         default=True
#     )

#     display_order = models.PositiveIntegerField(
#         default=0
#     )

#     class Meta:
#         ordering = ['display_order', 'name']

#     def __str__(self):
#         return self.name
    


# class PromptLibrary(models.Model):

#     PRIMARY = "PRIMARY"
#     SECONDARY = "SECONDARY"
#     TERTIARY = "TERTIARY"
#     GENERAL = "GENERAL"

#     SCHOOL_LEVELS = (
#         (PRIMARY, "Primary"),
#         (SECONDARY, "Secondary"),
#         (TERTIARY, "Tertiary"),
#         (GENERAL, "General"),
#     )

#     title = models.CharField(max_length=255)

#     category = models.ForeignKey(
#         PromptCategory,
#         on_delete=models.CASCADE
#     )

#     school_level = models.CharField(
#         max_length=20,
#         choices=SCHOOL_LEVELS,
#         default=GENERAL
#     )

#     subject = models.CharField(
#         max_length=100,
#         blank=True
#     )

#     prompt_text = models.TextField()

#     usage_count = models.PositiveIntegerField(
#         default=0
#     )

#     is_featured = models.BooleanField(
#         default=False
#     )

#     is_active = models.BooleanField(
#         default=True
#     )

#     created_at = models.DateTimeField(
#         auto_now_add=True
#     )


from django.db import models
from django.utils.text import slugify


class AIToolCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    icon = models.CharField(
        max_length=100,
        blank=True
    )

    display_order = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "AI Tool Category"
        verbose_name_plural = "AI Tool Categories"

    def __str__(self):
        return self.name


class PromptCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    slug = models.SlugField(
        unique=True,
        blank=True
    )

    display_order = models.PositiveIntegerField(
        default=0
    )

    is_active = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Prompt Category"
        verbose_name_plural = "Prompt Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AITool(models.Model):

    category = models.ForeignKey(
        AIToolCategory,
        on_delete=models.CASCADE,
        related_name='tools'
    )

    name = models.CharField(
        max_length=150
    )

    description = models.TextField()

    best_for = models.TextField(
        help_text="Comma separated tags"
    )

    website_url = models.URLField()

    icon_class = models.CharField(
        max_length=100,
        default='fas fa-robot'
    )

    is_featured = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    display_order = models.PositiveIntegerField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['display_order', 'name']

    @property
    def tags(self):
        return [
            tag.strip()
            for tag in self.best_for.split(',')
            if tag.strip()
        ]

    def __str__(self):
        return self.name


class PromptLibrary(models.Model):

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    TERTIARY = "TERTIARY"
    GENERAL = "GENERAL"

    SCHOOL_LEVELS = (
        (PRIMARY, "Primary"),
        (SECONDARY, "Secondary"),
        (TERTIARY, "Tertiary"),
        (GENERAL, "General"),
    )

    title = models.CharField(
        max_length=255
    )

    category = models.ForeignKey(
        PromptCategory,
        on_delete=models.CASCADE,
        related_name='prompts'
    )

    school_level = models.CharField(
        max_length=20,
        choices=SCHOOL_LEVELS,
        default=GENERAL
    )

    subject = models.CharField(
        max_length=100,
        blank=True
    )

    prompt_text = models.TextField()

    usage_count = models.PositiveIntegerField(
        default=0
    )

    is_featured = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['title']
        verbose_name = 'Prompt Library'
        verbose_name_plural = 'Prompt Libraries'

    def __str__(self):
        return self.title