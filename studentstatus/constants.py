"""
Status vocabulary for the student-status module.

Kept free of model/view imports so every layer (models, services, forms,
middleware, login backend) can share it without circular imports.

The values match Student.student_status in students/models.py.
"""

ACTIVE = 'active'
INACTIVE = 'inactive'
SUSPENDED = 'suspended'
DROPPED = 'dropped'
EXPELLED = 'expelled'
GRADUATED = 'graduated'

STATUS_LABELS = {
    ACTIVE: 'Active',
    INACTIVE: 'Inactive',
    SUSPENDED: 'Suspended',
    DROPPED: 'Dropped',
    EXPELLED: 'Expelled',
    GRADUATED: 'Graduated',
}
STATUS_CHOICES = list(STATUS_LABELS.items())

# Statuses an administrator may set from the front end.
# GRADUATED is deliberately absent: graduation (alumni move, GraduationRecord)
# is handled by the existing graduation logic, not here.
ASSIGNABLE_STATUSES = (ACTIVE, INACTIVE, SUSPENDED, DROPPED, EXPELLED)
ASSIGNABLE_CHOICES = [(s, STATUS_LABELS[s]) for s in ASSIGNABLE_STATUSES]

# Students in these statuses are read-only here — change them where they were set.
PROTECTED_STATUSES = (GRADUATED,)

# Students in these statuses can neither log in nor keep an existing session.
LOGIN_BLOCKED_STATUSES = (INACTIVE, SUSPENDED, DROPPED, EXPELLED, GRADUATED)

DEFAULT_BLOCK_MESSAGE = (
    "Your portal account is not active. Please contact the school administration."
)
BLOCK_MESSAGES = {
    INACTIVE: "Your account is currently inactive. Please contact the school administration.",
    SUSPENDED: "Your account has been suspended. Please contact the school administration.",
    DROPPED: "Your account is no longer active because your enrolment has ended. "
             "Please contact the school administration.",
    EXPELLED: "Your access to this portal has been withdrawn. "
              "Please contact the school administration.",
    GRADUATED: "You have graduated, so this portal account is no longer active. "
               "Please contact the school administration if you need your records.",
}


def block_message(status):
    """Message shown to a student who is blocked from the portal."""
    return BLOCK_MESSAGES.get(status, DEFAULT_BLOCK_MESSAGE)