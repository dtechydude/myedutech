from django.urls import path
from transport import views as transport_views


app_name = 'transport'

urlpatterns = [
    
    path('bus_route_list/', transport_views.bus_route_list, name="bus_route_list"),
    path('student_on_bus/', transport_views.student_on_bus, name="student_on_bus"),
    path('signup_for_bus/', transport_views.sign_up_bus, name="signup_for_bus"),
    path('create_bus_signup/', transport_views.create_bus_signup, name="create_bus_signup"),
    # path('my_route/', transport_views.my_route, name="my_route"),
    path('bus_signups/', transport_views.bus_signup_list, name='bus_signup_list'),
    path('my_route/', transport_views.student_own_route_detail, name='student_own_route_detail'),


    path('submission_success/', transport_views.submission_success, name="submission_success"),



    
]