from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from users import views as user_views 
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from curriculum.models import SchoolIdentity
from .views import SafePasswordResetView


# app_name ='users'
# We fetch the school data once here or inside the view
# school_data = SchoolIdentity.objects.first()

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='users/login.html'), name="login"),
    path('register/', user_views.user_registration, name="user-registeration"),
    
    # path('login/', user_views.user_login, name="user-login"),
    path('login/', user_views.CustomLoginView.as_view(), name='login'),

    path('registration/', user_views.register, name='register'),
    path('all-users/', user_views.all_users, name="all_users"),

    # path('login/', user_views.user_login, name="login"),
    path('dashboard/', user_views.users_home, name="users_home"),    
    path('profile/', user_views.profile_edit, name="profile"),
    path('employment_profile/', user_views.employment_edit, name="employment_profile"),
    path('logout/', user_views.user_logout, name='user_logout'),
    path('logout-success/', user_views.logout_success, name='logout_success'),

   
    # THIS WAS WORKING OOOO JUST DISTURBINT IN MIGRATION
    # path('password-reset/', 
    #  auth_views.PasswordResetView.as_view(
    #      template_name='users/password_reset.html',
    #      email_template_name='registration/password_reset_email_text.txt', # Text version
    #      html_email_template_name='registration/password_reset_email.html', # HTML version
    #      extra_email_context={'school_info': school_data} # School Information
    #  ), 
    #  name='password_reset'),
    path(
        'password-reset/',
        SafePasswordResetView.as_view(),
        name='password_reset'
    ),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'), name="password_reset_done"),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html', success_url = reverse_lazy('login')), name="password_reset_confirm"),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'), name="password_reset_complete"),


    path('enroll/', user_views.enroll_student, name='enroll_student'),
    path('enroll/details/', user_views.enroll_student_details, name='enroll_student_details'),
    # Add a URL for a success page
    path('enroll/success/', user_views.enroll_success, name='success_page'),
    path('check-username/', user_views.check_username, name='check_username'),

        
   
]
