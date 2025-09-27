# from django.contrib import admin, messages
# from .models import Hostel, Student, Badge, Parent
# from import_export.admin import ImportExportModelAdmin
# from django.shortcuts import render, redirect
# from django import forms
# from django.db import transaction
# from .models import Student # Your Student model
# # Import from the payments app
# from payments.models import StudentFeeAssignment, PaymentCategory, Term, Session 


# class HostelAdmin(admin.ModelAdmin):
#     list_display = ('name', 'hostel_master')
#     search_fields = ('name',)
#     ordering = ['name',]
#     raw_id_fields = ['hostel_master']
#     exclude = ('slug',)



# # class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
# #     list_display = ('user', 'USN', 'first_name', 'last_name', 'current_class','date_admitted', 'guardian_phone', 'student_status')
# #     list_filter = ['current_class', 'student_status',]

# #     # This is the corrected search_fields tuple
# #     search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')

# #     raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent',]
# #     autocomplete_fields = ['current_class', 'class_on_admission']
# #     exclude=('fee_balance',)
# #New Student Admin

# class StudentFeeAssignmentForm(forms.Form):
#     payment_category = forms.ModelChoiceField(queryset=PaymentCategory.objects.all(), label="Fee Category")
#     amount_due = forms.DecimalField(max_digits=10, decimal_places=2, label="Amount Due")
#     term = forms.ModelChoiceField(queryset=Term.objects.all(), label="Term")
#     session = forms.ModelChoiceField(queryset=Session.objects.all(), label="Session")

# @admin.register(Student)
# class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
#     list_display = ('user', 'USN', 'first_name', 'last_name', 'current_class', 'date_admitted', 'guardian_phone', 'student_status')
#     list_filter = ['current_class', 'student_status']
#     search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')
#     raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent']
#     autocomplete_fields = ['current_class', 'class_on_admission']
#     exclude = ('fee_balance',)

#     # Add the custom action to the list of actions
#     actions = ['assign_fees_to_students']

#     def assign_fees_to_students(self, request, queryset):
#         # This is the intermediate page logic
#         if 'apply' in request.POST:
#             form = StudentFeeAssignmentForm(request.POST)
#             if form.is_valid():
#                 payment_category = form.cleaned_data['payment_category']
#                 amount_due = form.cleaned_data['amount_due']
#                 term = form.cleaned_data['term']
#                 session = form.cleaned_data['session']
                
#                 with transaction.atomic():
#                     for student in queryset:
#                         StudentFeeAssignment.objects.update_or_create(
#                             student=student,
#                             payment_category=payment_category,
#                             term=term,
#                             session=session,
#                             defaults={'amount_due': amount_due}
#                         )
                
#                 self.message_user(
#                     request,
#                     f"Successfully assigned fees to {queryset.count()} students.",
#                     messages.SUCCESS
#                 )
#                 return redirect('admin:students_student_changelist') # Ensure this redirect matches your app and model name

#         form = StudentFeeAssignmentForm(
#             initial={
#                 'term': Term.objects.get(is_current=True) if Term.objects.filter(is_current=True).exists() else None,
#                 'session': Session.objects.get(is_current=True) if Session.objects.filter(is_current=True).exists() else None
#             }
#         )
#         context = {
#             'title': 'Assign Fees to Students',
#             'students': queryset,
#             'form': form,
#             'opts': self.model._meta,
#             'is_popup': False,
#             'save_as': self.save_as,
#             'has_permission': self.has_change_permission(request)
#         }
#         return render(request, 'admin/assign_fees.html', context)
    
#     assign_fees_to_students.short_description = "Assign fees to selected students"




# class BadgeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
#     list_display=('name', 'desc')
#     exclude=('slug',)

# # Register the Parent model so it's visible in the admin panel.
# @admin.register(Parent)
# class ParentAdmin(admin.ModelAdmin):
#     # This will display the associated user in the Parent list view.
#     list_display = ('user', 'guardian_name', 'guardian_address', 'guardian_phone')
#     search_fields = ('user__username',)
#     raw_id_fields = ['user',]



# # admin.site.register(StaffCategory)
# admin.site.register(Hostel, HostelAdmin)
# # admin.site.register(Student, StudentAdmin)
# admin.site.register(Badge, BadgeAdmin)
# # admin.site.register(Parent, ParentAdmin)


# students/admin.py

from django.contrib import admin, messages
from .models import Hostel, Student, Badge, Parent
from import_export.admin import ImportExportModelAdmin
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction

# Import models from the payments app
from payments.models import StudentFeeAssignment, PaymentCategory, Term, Session 

# Use @admin.register for all admin classes
@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostel_master')
    search_fields = ('name',)
    ordering = ['name',]
    raw_id_fields = ['hostel_master']
    exclude = ('slug',)

# Define the form for the admin action
class StudentFeeAssignmentForm(forms.Form):
    payment_category = forms.ModelChoiceField(queryset=PaymentCategory.objects.all(), label="Fee Category")
    amount_due = forms.DecimalField(max_digits=10, decimal_places=2, label="Amount Due")
    term = forms.ModelChoiceField(queryset=Term.objects.all(), label="Term")
    session = forms.ModelChoiceField(queryset=Session.objects.all(), label="Session")

@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('user', 'USN', 'first_name', 'last_name', 'current_class', 'date_admitted', 'guardian_phone', 'student_status')
    list_filter = ['current_class', 'student_status']
    search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')
    raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent']
    autocomplete_fields = ['current_class', 'class_on_admission']
    exclude = ('fee_balance',)

    actions = ['assign_fees_to_students']

    def assign_fees_to_students(self, request, queryset):
        if 'apply' in request.POST:
            form = StudentFeeAssignmentForm(request.POST)
            if form.is_valid():
                payment_category = form.cleaned_data['payment_category']
                amount_due = form.cleaned_data['amount_due']
                term = form.cleaned_data['term']
                session = form.cleaned_data['session']
                
                with transaction.atomic():
                    for student in queryset:
                        StudentFeeAssignment.objects.update_or_create(
                            student=student,
                            payment_category=payment_category,
                            term=term,
                            session=session,
                            defaults={'amount_due': amount_due}
                        )
                
                self.message_user(
                    request,
                    f"Successfully assigned fees to {queryset.count()} students.",
                    messages.SUCCESS
                )
                return redirect('admin:students_student_changelist')

        form = StudentFeeAssignmentForm(
            initial={
                'term': Term.objects.get(is_current=True) if Term.objects.filter(is_current=True).exists() else None,
                'session': Session.objects.get(is_current=True) if Session.objects.filter(is_current=True).exists() else None
            }
        )
        context = {
            'title': 'Assign Fees to Students',
            'students': queryset,
            'form': form,
            'opts': self.model._meta,
            'is_popup': False,
            'save_as': self.save_as,
            'has_permission': self.has_change_permission(request)
        }
        return render(request, 'admin/assign_fees.html', context)
    
    assign_fees_to_students.short_description = "Assign fees to selected students"

@admin.register(Badge)
class BadgeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display=('name', 'desc')
    exclude=('slug',)

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'guardian_name', 'guardian_address', 'guardian_phone')
    search_fields = ('user__username',)
    raw_id_fields = ['user',]