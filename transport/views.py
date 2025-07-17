from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F, Sum, Q
from transport.models import Route, StudentOnRoute
from transport.forms import BusPaymentForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import os
from students.models import Student
from django.http import HttpResponse
from django.http import FileResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import(ListView, FormView, CreateView, UpdateView, DeleteView, DetailView)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# For panigation
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# bus route list
@login_required
def bus_route_list(request):
    routelist = Route.objects.all()

    context = {
        'routelist': routelist,

    }
    return render (request, 'transport/bus_route_list.html', context )


# Students Approved On Bus
@login_required
def student_on_bus(request): 
    student_on_bus = StudentOnRoute.objects.all()   

    context = {
        'student_on_bus' : student_on_bus,              

    }
    
    return render (request, 'transport/student_onbus.html', context )

@login_required # Ensure only logged-in users can access this view
def sign_up_bus(request):
    if request.method == 'POST':
        form = BusPaymentForm(request.POST)
        if form.is_valid():
            # Don't save yet! We need to set the user first.
            submission = form.save(commit=False)
            submission.payee_id = request.user # Set the logged-in user
            submission.save()
            messages.success(request, f'The Bus Payment has been entered successfully')
            return redirect('transport:bus_payment_success') # Redirect to a success page
    else:
        form = BusPaymentForm()
    return render(request, 'transport/signup_for_bus.html', {'form': form})
   