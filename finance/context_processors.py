# finance/context_processors.py
"""
Adds `finance_unread_notifications_count` to every template's context,
mirroring the existing `unread_tickets_count` context processor pattern.

IMPORTANT — deliberately NOT named `unread_count`: if you register this
alongside a ticket/other context processor that also returns a key called
`unread_count`, Django silently lets whichever one runs LAST in
TEMPLATES[...]['OPTIONS']['context_processors'] win, overwriting the
other's value in every template's context. Giving this one its own
distinct key avoids that collision entirely — both bell icons can then
show correct, independent counts on the same page.
"""
from .models import PaymentNotification, NotificationReadStatus
from .permissions import is_finance_staff


def finance_unread_notifications_count(request):
    """
    Returns the count of pending payment notifications the logged-in
    finance staff member hasn't opened yet. Non-staff users (parents,
    students, teachers) always get 0 here — this badge is specifically for
    the school/bursary side seeing new notifications come in, not for
    parents/students seeing responses.
    """
    unread_count = 0

    if request.user.is_authenticated and is_finance_staff(request.user):
        read_notification_ids = NotificationReadStatus.objects.filter(
            user=request.user
        ).values_list('notify_id', flat=True)

        unread_count = PaymentNotification.objects.filter(
            status=PaymentNotification.Status.PENDING
        ).exclude(pk__in=read_notification_ids).count()

    return {'finance_unread_notifications_count': unread_count}