from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """
    Finance app configuration.

    Covers Invoicing, Payments & Receipts, Fee Structures, Expense Tracking
    and Profit & Loss reporting for the KwikSchools platform.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'
    verbose_name = 'Finance & Accounts'

    def ready(self):
        # Import signal handlers so they get registered when the app loads.
        import finance.signals  # noqa: F401
