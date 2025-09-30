# curriculum/admin.py

from curriculum.models import SchoolIdentity, Lesson, Subject, ELearningSubject, Session, Standard, ClassGroup, Term
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from import_export.admin import ImportExportModelAdmin
from payments.models import StudentFeeAssignment, ClassFeeTemplate, PaymentCategory 

class ClassFeeTemplateForm(forms.Form):
    fee_template = forms.ModelChoiceField(
        queryset=ClassFeeTemplate.objects.all(),
        label="Select Fee Template to Apply"
    )

class SchoolIdentityAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        if not change and self.model.objects.exists():
            messages.error(request, "There can be only one school identity instance. Please edit the existing one.")
        else:
            try:
                obj.save()
            except ValidationError as e:
                for error_msg in e.messages:
                    messages.error(request, error_msg)
    
    list_display = ('name', 'phone1', 'email')
    exclude = ['slug',]

class SessionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    exclude = ['slug']
    # ADDED: This fixes the autocomplete error.
    search_fields = ['name',]

@admin.register(Standard)
class StandardAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('name', 'promotion_order', 'form_teacher', 'desc')
    exclude = ['slug']
    search_fields = ['name',]
    autocomplete_fields = ['form_teacher']
    actions = ['apply_class_fee_template']

    def apply_class_fee_template(self, request, queryset):
        if 'apply' in request.POST:
            form = ClassFeeTemplateForm(request.POST)
            if form.is_valid():
                fee_template = form.cleaned_data['fee_template']
                students_count = 0
                fees_generated_count = 0
                
                with transaction.atomic():
                    for standard in queryset:
                        students = standard.students.all()  
                        students_count += students.count()
                        for student in students:
                            StudentFeeAssignment.objects.update_or_create(
                                student=student,
                                term=fee_template.term,
                                session=fee_template.session,
                                payment_category=fee_template.payment_category,
                                defaults={'amount_due': fee_template.amount_due}
                            )
                            fees_generated_count += 1
                
                messages.success(request, f"Successfully applied fee template to {students_count} students ({fees_generated_count} fee assignments created/updated).")
                return redirect(request.get_full_path())
            else:
                messages.error(request, "Please correct the form errors.")

        form = ClassFeeTemplateForm()
        context = {
            'form': form,
            'title': 'Apply Class Fee Template',
            'classes': queryset, 
            'request': request,
        }
        return render(request, 'admin/apply_class_fee_template.html', context)
    
    apply_class_fee_template.short_description = "Apply a class fee template to selected classes"

class ClassGroupAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('name', 'standard', 'form_teacher')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'name')
    autocomplete_fields = ['form_teacher']

class SubjectAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('subject_id', 'name', 'description')
    search_fields = ('subject_id', 'name')
    exclude = ['slug']

class ELearningSubjectAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('subject_id', 'name', 'standard', 'description')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'subject_id')
    exclude = ['slug']

class LessonAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('standard', 'subject', 'lesson_id', 'name')
    list_filter = ['standard',]
    search_fields = ('standard__name', 'subject__name')
    raw_id_fields = ['created_by',]
    exclude = ['slug']

class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    raw_id_fields = ('session',)
    # ADDED: This also needs search_fields for autocomplete
    search_fields = ['name', 'session__name']

@admin.register(ClassFeeTemplate)
class ClassFeeTemplateAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('student_class', 'payment_category', 'amount_due', 'term', 'session')
    list_filter = ('student_class', 'payment_category', 'term', 'session')
    search_fields = ('student_class__name', 'payment_category__name')
    autocomplete_fields = ['student_class', 'payment_category', 'term', 'session']
    actions = ['delete_selected']


# # Online Elearn integration
# @admin.register(SubjectOnlineMeeting)
# class SubjectOnlineMeetingAdmin(admin.ModelAdmin):
#     # What columns to show in the list view
#     list_display = (
#         'subject', 
#         'standard_name', # Custom method to show the Class Name
#         'platform', 
#         'is_active', 
#         'meeting_link'
#     )
    
#     # Filters on the right sidebar
#     list_filter = (
#         'is_active', 
#         'platform', 
#         'subject__standard' # Filter by the Class/Standard
#     )
    
#     # Fields to search across
#     search_fields = (
#         'subject__name', 
#         'subject__standard__name', 
#         'meeting_link'
#     )
    
#     # How the fields appear when adding/editing a link
#     fieldsets = (
#         ('Meeting Details', {
#             'fields': ('subject', 'platform', 'meeting_link', 'is_active'),
#             'description': 'Select the E-Learning Subject and provide the recurring meeting URL.'
#         }),
#     )

#     # --- Custom Methods ---

#     # Method to display the Standard/Class name in the list view
#     @admin.display(description='Class (Standard)', ordering='subject__standard__name')
#     def standard_name(self, obj):
#         return obj.subject.standard.name

#     # --- Permission Enforcement (Assuming Staff or a Custom Teacher flag) ---

#     def has_view_permission(self, request, obj=None):
#         """Allows viewing only if user is staff or a recognized teacher."""
#         # Assuming your User model/profile has an 'is_teacher' boolean/property
#         return request.user.is_staff or getattr(request.user, 'is_teacher', False)
    
#     def has_add_permission(self, request):
#         """Allows adding only if user is staff or a recognized teacher."""
#         return request.user.is_staff or getattr(request.user, 'is_teacher', False)

#     def has_change_permission(self, request, obj=None):
#         """Allows changing only if user is staff or a recognized teacher."""
#         return request.user.is_staff or getattr(request.user, 'is_teacher', False)

#     def has_delete_permission(self, request, obj=None):
#         """Allows deleting only if user is staff or a recognized teacher."""
#         # Teachers may only be allowed to delete their own links, but here we allow staff/all teachers
#         return request.user.is_staff or getattr(request.user, 'is_teacher', False)




admin.site.register(Session, SessionAdmin)
admin.site.register(ClassGroup, ClassGroupAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(ELearningSubject, ELearningSubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(SchoolIdentity, SchoolIdentityAdmin)
admin.site.register(Term, TermAdmin)
# The decorator @admin.register(ClassFeeTemplate) already handles this registration
# admin.site.register(ClassFeeTemplate, ClassFeeTemplateAdmin)

# This class is not being used or registered, so it can be safely removed.
# class MyModelAdmin(AdminVideoMixin, admin.ModelAdmin):
#     pass