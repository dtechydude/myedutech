# curriculum/admin.py
from curriculum.models import SchoolIdentity, Subject, Session, Standard, ClassGroup, Term
# NOTE: ELearningSubject/Lesson admin registrations moved to elearning/admin.py
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from import_export.admin import ImportExportModelAdmin
from payments.models import StudentFeeAssignment, ClassFeeTemplate, PaymentCategory 
from results.models import SessionResultStatus

# New Admin For Standard or School Identity
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import SchoolIdentity, StandardIdentity, PublicHoliday

# from .models import PublicHoliday




class PublicHolidayInline(admin.TabularInline):
    model = PublicHoliday
    extra = 1


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'start_date', 'end_date', 'is_current')
    raw_id_fields = ('session',)
    # ADDED: This also needs search_fields for autocomplete
    list_filter = ('session',)

    search_fields = ['name', 'session__name']

    inlines = [PublicHolidayInline]

class ClassFeeTemplateForm(forms.Form):
    fee_template = forms.ModelChoiceField(
        queryset=ClassFeeTemplate.objects.all(),
        label="Select Fee Template to Apply"
    )


class StandardIdentityInline(admin.TabularInline):
    model = StandardIdentity
    extra = 1  # Number of empty rows to show for mapping classes
    autocomplete_fields = ['standard'] # Optional: if your Standard model has search_fields



@admin.register(SchoolIdentity)
class SchoolIdentityAdmin(admin.ModelAdmin):
    # Updated: Allow adding up to 3 identities
    def has_add_permission(self, request):
        if self.model.objects.count() >= 3:
            return False
        return super().has_add_permission(request)

    def save_model(self, request, obj, form, change):
        # The 3-entry limit is already handled in the model's save() method,
        # but we can provide immediate feedback here as well.
        try:
            obj.save()
        except ValidationError as e:
            for error_msg in e.messages:
                messages.error(request, error_msg)

    list_display = ('identity_label', 'name', 'is_default', 'phone1', 'email')
    list_editable = ('is_default',) # Quickly toggle the main identity from the list view
    exclude = ['slug']
    
    # Allows you to map classes to this identity on the same page
    inlines = [StandardIdentityInline]

@admin.register(StandardIdentity)
class StandardIdentityAdmin(admin.ModelAdmin):
    list_display = ('standard', 'school_identity')
    list_filter = ('school_identity',)


# Session Report Card Admin
@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    exclude = ['slug']
    # ADDED: This fixes the autocomplete error.
    search_fields = ['name',]



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



# @admin.register(ClassGroup)
# class ClassGroupAdmin(ImportExportModelAdmin):
#     list_display = ('name', 'standard', 'form_teacher')
#     list_filter = ['standard__name']
#     search_fields = ('standard__name', 'name')
#     autocomplete_fields = ['form_teacher']

@admin.register(Subject)
class SubjectAdmin(ImportExportModelAdmin):
    list_display = ('subject_id', 'name', 'description')
    search_fields = ('subject_id', 'name')
    exclude = ['slug']

@admin.register(ClassFeeTemplate)
class ClassFeeTemplateAdmin(ImportExportModelAdmin):
    list_display = ('student_class', 'payment_category', 'amount_due', 'term', 'session')
    list_filter = ('student_class', 'payment_category', 'term', 'session')
    search_fields = ('student_class__name', 'payment_category__name')
    autocomplete_fields = ['student_class', 'payment_category', 'term', 'session']
    actions = ['delete_selected']



