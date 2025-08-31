from django.urls import path
from transport import views as transport_views


app_name = 'transport'

urlpatterns = [
    
    path('bus_route_list/', transport_views.bus_route_list, name="bus_route_list"),
    path('student_on_bus/', transport_views.student_on_bus, name="student_on_bus"),
    path('signup_for_bus/', transport_views.sign_up_bus, name="signup_for_bus"),
    # path('create_bus_signup/', transport_views.create_bus_signup, name="create_bus_signup"),
    # path('my_route/', transport_views.my_route, name="my_route"),
    path('bus_signups/', transport_views.bus_signup_list, name='bus_signup_list'),
    path('my_route/', transport_views.student_own_route_detail, name='student_own_route_detail'),

     # URL for students to sign themselves up
    path('signup/', transport_views.student_bus_signup_view, name='signup'),
    
    # URL for staff to sign up a student on their behalf
    path('staff/signup/', transport_views.staff_bus_signup_view, name='staff_signup'),

    # URL to view a student's payment pass
    path('payment-pass/<int:enrollment_id>/', transport_views.student_payment_pass_view, name='payment_pass'),
    path('enrollments/', transport_views.bus_enrollment_list_view, name='enrollment_list'),

      # New URL for a student to view their own pass
    path('my-pass/', transport_views.my_payment_pass_redirect_view, name='my_pass'),


    path('submission_success/', transport_views.submission_success, name="submission_success"),



    
]