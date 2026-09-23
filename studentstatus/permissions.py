def is_status_admin(user):
    """Only active superusers and staff (school administrators) may manage student status."""
    return bool(
        user is not None
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.is_staff)
    )