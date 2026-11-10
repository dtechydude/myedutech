from django.apps import AppConfig


class PagesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pages'


    def ready(self):
        from .l10n_patch import apply_integer_localization_patch
        apply_integer_localization_patch()
