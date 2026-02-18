# curriculum/admin.py
from curriculum.models import SchoolIdentity, Lesson, Subject, ELearningSubject, Session, Standard, ClassGroup, Term, GradingComponent
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from import_export.admin import ImportExportModelAdmin
from payments.models import StudentFeeAssignment, ClassFeeTemplate, PaymentCategory 
from results.models import SessionResultStatus

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


# Session Report Card Admin


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    exclude = ['slug']
    # ADDED: This fixes the autocomplete error.
    search_fields = ['name',]


# class SessionAdmin(ImportExportModelAdmin):
#     list_display = ('name', 'start_date', 'end_date', 'is_current')
#     exclude = ['slug']
#     # ADDED: This fixes the autocomplete error.
#     search_fields = ['name',]

@admin.register(Standard)
class StandardAdmin(ImportExportModelAdmin):
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

class ClassGroupAdmin(ImportExportModelAdmin):
    list_display = ('name', 'standard', 'form_teacher')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'name')
    autocomplete_fields = ['form_teacher']

class SubjectAdmin(ImportExportModelAdmin):
    list_display = ('subject_id', 'name', 'description')
    search_fields = ('subject_id', 'name')
    exclude = ['slug']

class ELearningSubjectAdmin(ImportExportModelAdmin):
    list_display = ('subject_id', 'name', 'standard', 'description')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'subject_id')
    exclude = ['slug']

class LessonAdmin(ImportExportModelAdmin):
    list_display = ('standard', 'subject', 'lesson_id', 'name')
    list_filter = ['standard',]
    search_fields = ('standard__name', 'subject__name')
    raw_id_fields = ['created_by',]
    exclude = ['slug']

@admin.register(Term)
class TermAdmin(ImportExportModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    raw_id_fields = ('session',)
    # ADDED: This also needs search_fields for autocomplete
    search_fields = ['name', 'session__name']

@admin.register(ClassFeeTemplate)
class ClassFeeTemplateAdmin(ImportExportModelAdmin):
    list_display = ('student_class', 'payment_category', 'amount_due', 'term', 'session')
    list_filter = ('student_class', 'payment_category', 'term', 'session')
    search_fields = ('student_class__name', 'payment_category__name')
    autocomplete_fields = ['student_class', 'payment_category', 'term', 'session']
    actions = ['delete_selected']


#GRADING ADMIN
# @admin.register(GradingComponent)
# class GradingComponentAdmin(admin.ModelAdmin):
#     list_display = ('school', 'name', 'weight', 'is_active')
#     list_filter = ('school', 'is_active')




# admin.site.register(Session, SessionAdmin)
admin.site.register(ClassGroup, ClassGroupAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(ELearningSubject, ELearningSubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(SchoolIdentity, SchoolIdentityAdmin)
# The decorator @admin.register(ClassFeeTemplate) already handles this registration
# admin.site.register(ClassFeeTemplate, ClassFeeTemplateAdmin)

# This class is not being used or registered, so it can be safely removed.
# class MyModelAdmin(AdminVideoMixin, admin.ModelAdmin):
#     pass