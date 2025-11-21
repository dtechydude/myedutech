# students/admin.py

from django.contrib import admin, messages
from .models import Hostel, Student, Badge, Parent, GraduationRecord
from import_export.admin import ImportExportModelAdmin
from django.shortcuts import render, redirect
from django import forms
from django.db import transaction
from django.http import HttpResponseRedirect # New import for the fix
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME # Import this!
from curriculum.models import Session, Term, Standard
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

# STUDENT BADGE
@admin.register(Badge)
class BadgeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display=('name', 'desc')
    exclude=('slug',)

@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('user', 'guardian_name', 'guardian_address', 'guardian_phone')
    search_fields = ('user__username',)
    raw_id_fields = ['user',]

# Define the form for the admin action
class StudentFeeAssignmentForm(forms.Form):
    payment_category = forms.ModelChoiceField(queryset=PaymentCategory.objects.all(), label="Fee Category")
    amount_due = forms.DecimalField(max_digits=10, decimal_places=2, label="Amount Due")
    term = forms.ModelChoiceField(queryset=Term.objects.all(), label="Term")
    session = forms.ModelChoiceField(queryset=Session.objects.all(), label="Session")


# # 1. Fee Assignment Form Definition
# # ------------------------------------------------
# class StudentFeeAssignmentForm(forms.Form):
#     payment_category = forms.ModelChoiceField(
#         queryset=PaymentCategory.objects.all(), 
#         label='Payment Category'
#     )
#     amount_due = forms.IntegerField(label='Amount Due')
#     term = forms.ModelChoiceField(queryset=Term.objects.all(), label='Term')
#     session = forms.ModelChoiceField(queryset=Session.objects.all(), label='Session')

# # ------------------------------------------------
# # Student Admin Configuration
# # ------------------------------------------------
# @admin.register(Student)
# class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
#     list_display = ('user', 'USN', 'first_name', 'last_name', 'current_class', 'date_admitted', 'guardian_phone', 'student_status')
#     list_filter = ['current_class', 'student_status']
#     search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')
#     raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent',]
#     exclude = ['fee_balance']

#     actions = ['assign_fees_to_students', 'graduate_selected_students']

#     @admin.action(description='Assign fees to selected students')
#     def assign_fees_to_students(self, request, queryset):
#         SELECTED_ACTION_KEY = ACTION_CHECKBOX_NAME

#         if 'apply' in request.POST:
#             form = StudentFeeAssignmentForm(request.POST)

#             # ✅ Correct way to retrieve multiple IDs from hidden fields
#             selected_pks = request.POST.getlist(SELECTED_ACTION_KEY)
#             students_to_save = Student.objects.filter(pk__in=selected_pks)

#             if form.is_valid():
#                 payment_category = form.cleaned_data['payment_category']
#                 amount_due = form.cleaned_data['amount_due']
#                 term = form.cleaned_data['term']
#                 session = form.cleaned_data['session']

#                 try:
#                     with transaction.atomic():
#                         fees_assigned = 0

#                         for student in students_to_save:
#                             StudentFeeAssignment.objects.update_or_create(
#                                 student=student,
#                                 payment_category=payment_category,
#                                 term=term,
#                                 session=session,
#                                 defaults={'amount_due': amount_due}
#                             )
#                             fees_assigned += 1

#                     self.message_user(
#                         request,
#                         f"Successfully assigned fees to {fees_assigned} students.",
#                         messages.SUCCESS
#                     )
#                     return HttpResponseRedirect(request.get_full_path())

#                 except Exception as e:
#                     self.message_user(request, f"Fee assignment failed: {e}", messages.ERROR)

#             selected = selected_pks  # fallback if form is invalid

#         else:
#             # GET request – render form
#             current_term = Term.objects.filter(is_current=True).first()
#             current_session = Session.objects.filter(is_current=True).first()

#             form = StudentFeeAssignmentForm(
#                 initial={
#                     'term': current_term.pk if current_term else None,
#                     'session': current_session.pk if current_session else None,
#                 }
#             )

#             selected = list(queryset.values_list('pk', flat=True).distinct())

#         students_for_display = Student.objects.filter(pk__in=selected)

#         context = {
#             'title': 'Assign Fees to Students',
#             'students': students_for_display,
#             'form': form,
#             'opts': self.model._meta,
#             'action_checkbox_name': SELECTED_ACTION_KEY,
#             'selected_ids': selected,  # now a list, not a string
#             'is_popup': False,
#             'save_as': self.save_as,
#             'has_permission': self.has_change_permission(request),
#         }

#         return render(request, 'admin/assign_fees.html', context)




# @admin.register(GraduationRecord)
# class GraduationRecordAdmin(admin.ModelAdmin):
#     list_display = ('student', 'session', 'graduated_class', 'date_graduated')
#     list_filter = ('session', 'graduated_class', 'date_graduated')
#     search_fields = ('student__first_name', 'student__last_name', 'student__USN')





# ----------------------------- Graduate Students Admin Action ----------------------------- #
@admin.action(description="Graduate selected students")
def graduate_selected_students(self, request, queryset):
   
    SELECTED_ACTION_KEY = ACTION_CHECKBOX_NAME

    if 'apply' in request.POST:
        # POST: Process graduation
        session_id = request.POST.get('session')
        session = Session.objects.filter(pk=session_id).first()

        if not session:
            self.message_user(request, "Please select a valid session.", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

        graduated_count = 0
        try:
            with transaction.atomic():
                # Create Alumni class if it does not exist
                alumni_class, created = Standard.objects.get_or_create(name="Alumni / Graduated")

                for student in queryset:
                    student.current_class = alumni_class
                    student.student_status = 'graduated'
                    student.graduated_session = session
                    student.save()

                    # Record graduation history
                    GraduationRecord.objects.create(
                        student=student,
                        graduated_class=alumni_class,
                        session=session
                    )
                    graduated_count += 1

            self.message_user(
                request,
                f"Successfully graduated {graduated_count} students.",
                messages.SUCCESS
            )

        except Exception as e:
            self.message_user(request, f"Graduation failed: {e}", messages.ERROR)

        return HttpResponseRedirect(request.get_full_path())

    else:
        # GET: Show session selection form
        current_session = Session.objects.filter(is_current=True).first()
        selected = list(queryset.values_list('pk', flat=True))

        context = {
            'title': 'Graduate Selected Students',
            'students': queryset,
            'session': current_session,
            'action_checkbox_name': SELECTED_ACTION_KEY,
            'selected_ids': selected,
            'opts': self.model._meta,
        }
        return render(request, 'admin/graduate_students.html', context)


# ----------------------------- Student Admin ----------------------------- #
@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = (
        'user', 'USN', 'first_name', 'last_name', 
        'current_class', 'date_admitted', 'guardian_phone', 'student_status'
    )
    list_filter = ['current_class', 'student_status']
    search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')
    raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent']
    exclude = ['fee_balance']

    actions = ['assign_fees_to_students', graduate_selected_students]

    # ----------------- Existing Fee Assignment Action (Unchanged) ----------------- #
    @admin.action(description='Assign fees to selected students')
    def assign_fees_to_students(self, request, queryset):
        SELECTED_ACTION_KEY = ACTION_CHECKBOX_NAME
        

        if 'apply' in request.POST:
            form = StudentFeeAssignmentForm(request.POST)
            selected_pks = request.POST.getlist(SELECTED_ACTION_KEY)
            students_to_save = Student.objects.filter(pk__in=selected_pks)

            if form.is_valid():
                payment_category = form.cleaned_data['payment_category']
                amount_due = form.cleaned_data['amount_due']
                term = form.cleaned_data['term']
                session = form.cleaned_data['session']

                try:
                    with transaction.atomic():
                        fees_assigned = 0
                        for student in students_to_save:
                            StudentFeeAssignment.objects.update_or_create(
                                student=student,
                                payment_category=payment_category,
                                term=term,
                                session=session,
                                defaults={'amount_due': amount_due}
                            )
                            fees_assigned += 1

                    self.message_user(
                        request,
                        f"Successfully assigned fees to {fees_assigned} students.",
                        messages.SUCCESS
                    )
                    return HttpResponseRedirect(request.get_full_path())

                except Exception as e:
                    self.message_user(request, f"Fee assignment failed: {e}", messages.ERROR)

            selected = selected_pks  # fallback if form invalid
        else:
            current_term = Term.objects.filter(is_current=True).first()
            current_session = Session.objects.filter(is_current=True).first()
            form = StudentFeeAssignmentForm(
                initial={
                    'term': current_term.pk if current_term else None,
                    'session': current_session.pk if current_session else None,
                }
            )
            selected = list(queryset.values_list('pk', flat=True).distinct())

        students_for_display = Student.objects.filter(pk__in=selected)

        context = {
            'title': 'Assign Fees to Students',
            'students': students_for_display,
            'form': form,
            'opts': self.model._meta,
            'action_checkbox_name': SELECTED_ACTION_KEY,
            'selected_ids': selected,
            'is_popup': False,
            'save_as': self.save_as,
            'has_permission': self.has_change_permission(request),
        }

        return render(request, 'admin/assign_fees.html', context)


# ----------------------------- Graduation Record Admin ----------------------------- #
@admin.register(GraduationRecord)
class GraduationRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'graduated_class', 'date_graduated')
    list_filter = ('session', 'graduated_class', 'date_graduated')
    search_fields = ('student__first_name', 'student__last_name', 'student__USN')