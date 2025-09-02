from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Ticket, Comment
from .forms import TicketForm, CommentForm
from django.core.paginator import Paginator, EmptyPage
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()



@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.author = request.user
            ticket.save()
            
            # Message for the ticket author
            messages.success(request, 'Your ticket has been submitted successfully!')
            
            # Send email notification to admins
            try:
                subject = f'New Support Ticket: {ticket.title}'
                message = f'A new support ticket has been submitted by {request.user.get_full_name} ({request.user.username}).\n\nTicket ID: #{ticket.id}\nTitle: {ticket.title}\nCategory: {ticket.category}\n\nView Ticket: http://127.0.0.1:8000/tickets/admin/{ticket.id}/'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [admin.email for admin in User.objects.filter(is_staff=True)]
                
                send_mail(subject, message, from_email, recipient_list)
            except Exception as e:
                # Log the error or handle it as needed
                print(f"Error sending email: {e}")
            
            return redirect('tickets:ticket_list')
    else:
        # This is the crucial part that was missing or incorrect.
        # Handle GET requests by rendering the empty form.
        form = TicketForm()
    
    return render(request, 'tickets/create_ticket.html', {'form': form})

@login_required
def ticket_list(request):
    # Filter tickets by the current logged-in user
    all_tickets = request.user.tickets_submitted.all().order_by('-created_at')

    # Add pagination logic
    paginator = Paginator(all_tickets, 10)  # Show 10 tickets per page
    page_number = request.GET.get('page')
    try:
        tickets = paginator.page(page_number)
    except EmptyPage:
        # If the page is out of range, deliver the last page of results
        tickets = paginator.page(paginator.num_pages)
    except:
        # If page number is not an integer, deliver first page
        tickets = paginator.page(1)

    return render(request, 'tickets/ticket_list.html', {'tickets': tickets})


@login_required
def ticket_detail(request, pk):
    # CORRECT THE QUERY:
    # This view also needs the change from 'student' to 'author'.
    ticket = get_object_or_404(Ticket, pk=pk, author=request.user)
    comments = ticket.comments.all().order_by('created_at')
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.save()
            return redirect('tickets:ticket_detail', pk=pk)
    else:
        form = CommentForm()
    return render(request, 'tickets/ticket_detail.html', {'ticket': ticket, 'comments': comments, 'form': form})

# ... (the rest of your views) ...

# Admin Views
# Admin Views
@login_required
def admin_ticket_list(request):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('pages:portal-home')

    # Get the category from the URL query parameters
    selected_category = request.GET.get('category')
    
    # Filter the queryset based on the selected category
    if selected_category:
        all_tickets = Ticket.objects.filter(category=selected_category).order_by('-created_at')
    else:
        all_tickets = Ticket.objects.all().order_by('-created_at')

    # Add pagination
    paginator = Paginator(all_tickets, 10)  # Show 10 tickets per page
    page_number = request.GET.get('page')
    try:
        tickets = paginator.page(page_number)
    except EmptyPage:
        tickets = paginator.page(paginator.num_pages)
    except:
        tickets = paginator.page(1)
    
    # Pass all unique categories to the template for the filter dropdown
    categories = Ticket.CATEGORY_CHOICES
        
    return render(request, 'tickets/admin_ticket_list.html', {
        'tickets': tickets,
        'categories': categories,
        'selected_category': selected_category
    })


@login_required
def admin_ticket_detail(request, pk):
    # ... (permission check) ...

    ticket = get_object_or_404(Ticket, pk=pk)
    comments = ticket.comments.all().order_by('created_at')

    if request.method == 'POST':
        if 'close_ticket' in request.POST:
            if ticket.status != 'Closed':
                ticket.status = 'Closed'
                ticket.save()
                messages.success(request, 'Ticket has been successfully closed.')
                return redirect('admin_ticket_detail', pk=pk)
            
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.ticket = ticket
            comment.author = request.user
            comment.is_admin_response = True
            comment.save()
            # Add a success message for the admin who sent the reply
            messages.success(request, 'Your response has been sent to the ticket author.')
            return redirect('admin_ticket_detail', pk=pk)
    else:
        form = CommentForm()

    return render(request, 'tickets/admin_ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'form': form
    })