# tickets/context_processors.py

from .models import Ticket, TicketReadStatus
from django.db.models import Q

def unread_tickets_count(request):
    """
    Returns the count of unread tickets for the logged-in user.
    """
    unread_count = 0
    if request.user.is_authenticated:
        read_tickets_ids = TicketReadStatus.objects.filter(user=request.user).values_list('ticket_id', flat=True)

        if request.user.is_staff:
            # Admins see all unread tickets
            all_tickets = Ticket.objects.all()
        elif hasattr(request.user, 'student'):
            # Students see their own unread tickets and relevant broadcasts
            all_tickets = Ticket.objects.filter(Q(author=request.user) | Q(is_broadcast=True, audience='students'))
        else:
            # Other users (e.g., teachers) see their own unread tickets and relevant broadcasts
            all_tickets = Ticket.objects.filter(Q(author=request.user) | Q(is_broadcast=True, audience='teachers'))

        unread_count = all_tickets.exclude(pk__in=read_tickets_ids).count()

    return {'unread_count': unread_count}