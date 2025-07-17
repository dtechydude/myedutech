from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponseForbidden
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F, Sum, Q
from transport.models import Route, BusFee, StudentBusPayment
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
        'routelist': Route.objects.all(),
        'routelist' : routelist,      

    }
    return render (request, 'transport/bus_route_list.html', context )

#Bus Fare List
# bus route list
@login_required
def bus_fare_list(request):
    routelist = BusFee.objects.all()

    context = {
        'routelist': BusFee.objects.all(),
        'routelist' : routelist,      

    }
    return render (request, 'transport/bus_fees_table.html', context )

# Students Approved On Bus
@login_required
def student_on_bus(request): 
    paymentlist = StudentBusPayment.objects.all()   

    context = {
        'paymentlist': StudentBusPayment.objects.all(),
        'paymentlist' : paymentlist,              

    }
    if paymentlist:
        return render (request, 'transport/student_onbus.html', context )
    else:
        return HttpResponse ('You have not made payment' )
   
   
# Student View Self Bus Payment
@login_required
def view_self_bus_payments(request):   
    mypayment = StudentBusPayment.objects.filter(payee_id=User.objects.get(username=request.user))
    context = {
     
        'mypayment' : StudentBusPayment.objects.filter(payee_id=User.objects.get(username=request.user)).order_by("payment_date_a"),

        'mypayment':mypayment,
    }

    return render(request, 'transport/bus_self_payment.html', context)


@login_required
def bus_payment_chart(request):
    payment_chart_list = BusFee.objects.all()
  
    context = {
        'payment_chart_list': BusFee.objects.all(),
        'payment_chart_list' : payment_chart_list

    }
    return render (request, 'payments/bus_fees_table.html', context )



# FUNCTION FOR DOWNLOADING FILE
def download(request,path):
    file_path=os.path.join(settings.MEDIA_ROOT,path)
    if os.path.exists(file_path):
        with open(file_path, 'rb')as fh:
            response=HttpResponse(fh.read(),content_type="application/file")
            response['Content-Disposition']='inline;filename='+os.path.basename(file_path)
            return response

    raise Http404


#  Function for pdf and csv

# Generate a PDF staff list
def allpayment_pdf(request):
    # create Bytestream buffer
    buf = io.BytesIO()
    #create a canvas
    c = canvas.Canvas(buf, pagesize=letter, bottomup=0)
    # create a text object
    textob = c.beginText()
    textob.setTextOrigin(inch, inch)
    textob.setFont("Helvetica", 12)
    # Add some lines of text
    # lines = [
    #     "This is line 1",
    #     "This is line 2",
    #     "This is line31",
    #     "This is line 4",
    # ]
    # Designate the model
    payment = PaymentDetail.objects.all()

    # Create a blank list

    lines = [" PAYMENT DETAIL REPORT"]

    for payments in payment:
        lines.append(""),
        lines.append("Username: " + payments.user.username),
        lines.append("Amount: " + str(payments.amount_paid_a)),
        lines.append("Date: " + str(payments.payment_date_a)),
        lines.append("Method:" + payments.other_details_a),

        lines.append("------->----------->----------->"),


    # loop
    for line in lines:
        textob.textLine(line)
    #fininsh up
    c.drawText(textob)
    c.showPage()
    c.save()
    buf.seek(0)
    # Return something
    return FileResponse(buf, as_attachment=False, filename='payment.pdf')


# Generate a CSV staff list
def allpayment_csv(request):
    response = HttpResponse(content_type ='text/csv')
    response['Content-Disposition'] = 'attachment; filename=payment-detail.csv'

# Create a csv writer
    writer = csv.writer(response)

    payment = StudentBusPayment.objects.all()

    # Add column headings to the csv files
    writer.writerow(['STD.ID', 'STUDENT DETAIL ', 'SESSION', 'TERM', 'FEE DUE',  'PURPOSE', 'PAID_1', 'DATE_1', 'METHOD_1', 'CHECKED_1', 'PAID_2', 'DATE_2', 'METHOD_2', 'CHECKED_2', 'PAID_3', 'DATE_3', 'METHOD_3', 'CHECKED_3', 'TOTAL PAID', 'TOTAL DEBT'])


    # Loop thru and output
    for payments in payment:
        
        # writer.writerow([payments.student_detail.user.username, payments.student_detail.last_name, payments.student_detail.first_name, payments.student_detail.current_class, payments.payment_name.session, payments.payment_name.term, payments.payment_name.amount_due, payments.payment_name, payments.amount_paid_a, payments.payment_date_a, payments.bank_name_a, payments.confirmed_a,
        #  payments.amount_paid_b, payments.payment_date_b, payments.bank_name_b, payments.confirmed_b, payments.amount_paid_c, payments.payment_date_c, payments.bank_name_c, payments.confirmed_c, payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c, payments.payment_name.amount_due - (payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c) ])

        writer.writerow([  payments.student_id, payments.student_detail, payments.payment_name.session, payments.payment_name.term, payments.payment_name.amount_due, payments.payment_name, payments.amount_paid_a, payments.payment_date_a, payments.bank_name_a, payments.confirmed_a,
         payments.amount_paid_b, payments.payment_date_b, payments.bank_name_b, payments.confirmed_b, payments.amount_paid_c, payments.payment_date_c, payments.bank_name_c, payments.confirmed_c, payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c, payments.payment_name.amount_due - (payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c) ])

    return response

 
def payment_chart_pdf(request):
    # create Bytestream buffer
    buf = io.BytesIO()
    #create a canvas
    c = canvas.Canvas(buf, pagesize=letter, bottomup=0)
    # create a text object
    textob = c.beginText()
    textob.setTextOrigin(inch, inch)
    textob.setFont("Helvetica", 12)
    # Add some lines of text

    # Designate the model
    payment_chart = PaymentChart.objects.all()

    # Create a blank list

    lines = [" PAYMENT CHART "]

    for payment in payment_chart:
        lines.append(""),
        lines.append("PAYMENT NAME: " + payment.name),
        lines.append("CATEGORY: " + str(payment.payment_cat)),
        lines.append("SESSION: " + str(payment.session)),
        lines.append("TERM:" + payment.term),
        lines.append("AMOUNT:" + payment.amount_due),

        lines.append("------->----------->----------->"),


    # loop
    for line in lines:
        textob.textLine(line)
    #fininsh up
    c.drawText(textob)
    c.showPage()
    c.save()
    buf.seek(0)
    # Return something
    return FileResponse(buf, as_attachment=False, filename='payment_chart.pdf')


# Generate a CSV staff list
def payment_chart_csv(request):
    response = HttpResponse(content_type ='text/csv')
    response['Content-Disposition'] = 'attachment; filename=payment_chart.csv'

# Create a csv writer
    writer = csv.writer(response)

    payment_chart = PaymentChart.objects.all()

    # Add column headings to the csv files
    writer.writerow(['PAYMENT NAME ', 'CATEGORY', 'SESSION', 'TERM', 'AMOUNT DUE',])


    # Loop thru and output
    for payment in payment_chart:
        writer.writerow([payment.name, payment.payment_cat, payment.session,
        payment.term, payment.amount_due,])

    return response

#This code generates the receipt
class StudentBusPaymentView(LoginRequiredMixin, DetailView):
    model = StudentBusPayment
    context_object_name = 'my_receipt'
    template_name = 'transport/receipt.html'
    

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        new_str = self.kwargs.get('pk') or self.request.GET.get('pk') or None

        queryset = queryset.filter(pk=new_str)
        obj = queryset.get()
        return obj


    
@login_required
def confirmed_payment(request):
    confirmed = StudentBusPayment.objects.all()
    return render(request, 'transport/confirmed_payment.html', {'confirmed':confirmed})


@login_required
def bus_debtor_list(request):
    debtorlist = StudentBusPayment.objects.all()
   
    balance_pay = StudentBusPayment.objects.annotate(balance_pay= F('amount_paid_a') + ('amount_paid_b') + ('amount_paid_c')- F('payment_name__amount_due'))

    # debtorlist = paymentreport_filter.qs
    page = request.GET.get('page', 1)
    paginator = Paginator(debtorlist, 40)
    try:
        debtorlist = paginator.page(page)
    except PageNotAnInteger:
        debtorlist = paginator.page(1)
    except EmptyPage:
        debtorlist = paginator.page(paginator.num_pages)


    context = {
        # 'debtorlist': PaymentDetail.objects.all(),
        # 'paymentreport_filter': paymentreport_filter,
        'debtorlist' : debtorlist,
        'balance_pay': balance_pay,
        # 'total_pay': total_pay,
        'balance_pay' : StudentBusPayment.objects.annotate(balance_pay= F('amount_paid_a') +('amount_paid_b') + ('amount_paid_c') - F('payment_name__amount_due')),
   
    }
   
    return render(request, 'payments/debtor_report.html', context )

#CSV file Download
def debtor_csv(request):
    response = HttpResponse(content_type ='text/csv')
    response['Content-Disposition'] = 'attachment; filename=debtors_list.csv'

# Create a csv writer
    writer = csv.writer(response)

    payment = StudentBusPayment.objects.all()

    # Add column headings to the csv files
    writer.writerow(['STD.ID', 'FIRST NAME ', 'LAST NAME', 'SESSION', 'FEE DUE',  'PURPOSE', 'TOTAL PAID', 'TOTAL DEBT'])


    # Loop thru and output
    for payments in payment:
        
        writer.writerow([ payments.payee, payments.payee.first_name, payments.payee.last_name, payments.payment_name.session, payments.payment_name.amount_due, payments.payment_name, payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c, payments.payment_name.amount_due - (payments.amount_paid_a + payments.amount_paid_b + payments.amount_paid_c)])

    return response


#Update self-payment  
class PaymentUpdateView(LoginRequiredMixin, UpdateView):
    fields = ('amount_paid_a', 'payment_date_a', 'bank_name_a', 
              'amount_paid_b', 'payment_date_b', 'bank_name_b',
              'amount_paid_c', 'payment_date_c', 'bank_name_c',)
    model = StudentBusPayment
    template_name = 'payment/payment_update_form.html'
    # context_object_name = 'payment_update'
    
    
    def form_valid(self, form):
        form.instance.payee = self.request.user
        return super().form_valid(form)

    def test_func(self):
        paymentdetail = self.get_object()
        if self.request.user == paymentdetail.payee:
            return True
        return False
    


# RECEIPT PDF FILE

@login_required
def receipt_render_pdf_view(request, *args, **kwargs):    

    pk = kwargs.get('pk')
    
    my_receipt = get_object_or_404(StudentBusPayment, pk=pk)
    template_path = 'payments/receipt_pdf.html'
    # template_path = 'results/result_sheet.html'
    context = {'my_receipt': my_receipt, 'bank_detail':bank_detail}
    # Create a Django response object, and specify content_type as pdf
    response = HttpResponse(content_type='application/pdf')
    # if you want to download
    # response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    # if you just want to display
    response['Content-Disposition'] = 'filename="receipt.pdf"'

    # find the template and render it.
    template = get_template(template_path)
    html = template.render(context)

    # create a pdf
    pisa_status = pisa.CreatePDF(
    html, dest=response)
    # if error then show some funy view
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response



@login_required # Ensure only logged-in users can access this view
def create_payment(request):
    if request.method == 'POST':
        form = PaymentCreateForm1(request.POST)
        if form.is_valid():
            # Don't save yet! We need to set the user first.
            submission = form.save(commit=False)
            submission.payee = request.user # Set the logged-in user
            submission.save()
            return redirect('payments:submission_success') # Redirect to a success page
    else:
        form = PaymentCreateForm1()
    return render(request, 'payments/create_submission.html', {'form': form})


def submission_success(request):
    return render(request, 'payments/create_submission_success.html')



@login_required
def receipt1_render_pdf_view(request, *args, **kwargs):  

    pk = kwargs.get('pk')
    
    my_receipt = get_object_or_404(PaymentDetail1, pk=pk)
    bank_detail = BankDetail.objects.all()
    school_id = SchoolIdentity.objects.all()
    template_path = 'payments/student_receipt_pdf.html'
    # template_path = 'results/result_sheet.html'
    context = {'my_receipt': my_receipt, 'bank_detail':bank_detail, 'school_id':school_id}
    # Create a Django response object, and specify content_type as pdf
    response = HttpResponse(content_type='application/pdf')
    # if you want to download
    # response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    # if you just want to display
    response['Content-Disposition'] = 'filename="receipt.pdf"'

    # find the template and render it.
    template = get_template(template_path)
    html = template.render(context)

    # create a pdf
    pisa_status = pisa.CreatePDF(
    html, dest=response)
    # if error then show some funy view
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response



@login_required # Ensure only logged-in users can access this view
def create_bus_payment(request):
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


def bus_payment_success(request):
    return render(request, 'transport/bus_signup_success.html')
