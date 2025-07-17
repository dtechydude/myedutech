from django.urls import path
from transport import views as payment_views
from . import views


app_name = 'transport'

urlpatterns = [
    # path('bus-payment-list/', payment_views.bus_paymentlist, name="bus_payment_list"),
    # path('my-bus-payment/', payment_views.view_self_bus_payments, name="my_bus_payment"),      
    # path('bus_payment_chart/', payment_views.bus_payment_chart, name="bus_payment_chart"),
    path('bus_route_list/', payment_views.bus_route_list, name="bus_route_list"),
    # path('bus_fare_list/', payment_views.bus_fare_list, name="bus_fare_list"),
    path('student_on_bus/', payment_views.student_on_bus, name="student_on_bus"),

    # path('signup_for_bus/', payment_views.create_bus_payment, name="signup_for_bus"),
    # path('bus_payment/success/', views.bus_payment_success, name='bus_payment_success'),

    
]