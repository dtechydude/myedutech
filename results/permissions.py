def get_session_comment_permissions(user, standard):
    """
    Returns (can_edit_teacher_comment, can_edit_principal_comment) for a
    given Standard (class), used by both the single-student report card
    and the bulk class comment-entry page.
    """
    if user.is_superuser or user.is_staff:
        return True, True

    is_principal = user.groups.filter(name='Principal/HeadTeacher').exists()

    is_form_teacher = (
        hasattr(user, 'teacher')
        and standard is not None
        and standard.form_teacher_id == user.teacher.id
    )

    return is_form_teacher, is_principal