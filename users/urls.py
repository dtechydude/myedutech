from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from users import views as user_views 
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


app_name ='users'

urlpatterns = [
    path('', auth_views.LoginView.as_view(template_name='users/login.html'), name="login"),
    path('register/', user_views.user_registration, name="user-registeration"),
    path('login/', user_views.user_login, name="user-login"),
    path('registration/', user_views.register, name='register'),
    path('all-users/', user_views.all_users, name="all_users"),

    # path('login/', user_views.user_login, name="login"),
    path('dashboard/', user_views.users_home, name="users_home"),    
    path('profile/', user_views.profile_edit, name="profile"),
    path('employment_profile/', user_views.employment_edit, name="employment_profile"),
    path('logout/', user_views.user_logout, name='user_logout'),
    
    # path('password-reset/', auth_views.PasswordResetView.as_view(template_name='users/password_reset.html'), name="password_reset"),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='users/password_reset.html', success_url = reverse_lazy('users:password_reset_done')), name="password_reset"),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'), name="password_reset_done"),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html', success_url = reverse_lazy('users:login')), name="password_reset_confirm"),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'), name="password_reset_complete"),
    
   
]
