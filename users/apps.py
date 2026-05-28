from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'


    def ready(self):
        import users.signals



# from django.apps import AppConfig


# class AccountsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'users'          # ← change to your actual app name
#     verbose_name = 'Users'

#     def ready(self):
#         import users.signals  # noqa — connects the pre_save signal
#         # ↑ change 'accounts' to match your app name

