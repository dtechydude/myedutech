from django.urls import path
from curriculum import views as curriculum_view


app_name = 'curriculum'

# =====================================================================
# ✅ E-LEARNING URLS MOVED OUT — now in the independent `elearning` app
# ---------------------------------------------------------------------
# standard_list, my-standard, subject_list, lesson_list, lesson_create,
# lesson_detail, lesson_update, lesson_delete now live in elearning/urls.py
# under their OWN 'elearning' namespace, mounted at their OWN URL prefix
# (e.g. path('elearning/', include('elearning.urls'))) — see the README.
#
# ⚠️ Unlike a previous version of this split, this one does NOT keep the
# old 'curriculum' namespace/prefix for e-learning routes. Anything that
# calls {% url 'curriculum:lesson_detail' ... %} (or lesson_list/
# lesson_create/lesson_update/lesson_delete/standard_list/subject_list/
# my-standard) needs to be updated to {% url 'elearning:lesson_detail' %}
# etc. — see the README for a grep command to find every place that
# needs updating.
# =====================================================================

urlpatterns = [
    path('', curriculum_view.ClassListView.as_view(), name='standard_list'),

    path('class_group_form_teacher/', curriculum_view.classgroup_form_teachers_list, name="classgroup_form_teachers"),
    path('form_teacher_head/', curriculum_view.form_teachers_head_list, name="form_teachers_head"),
    path('class-list/', curriculum_view.class_list, name="class_list"),
]
