def get_session_comment_permissions(user, student):
    """
    Returns (can_edit_teacher_comment, can_edit_principal_comment).
    Uses Student.form_teacher directly since it's kept in sync with
    Standard.form_teacher automatically.
    """
    if user.is_superuser or user.is_staff:
        return True, True

    is_principal = user.groups.filter(name='Principal/HeadTeacher').exists()

    is_form_teacher = (
        hasattr(user, 'teacher')
        and student.form_teacher_id is not None
        and student.form_teacher_id == user.teacher.id
    )

    return is_form_teacher, is_principal