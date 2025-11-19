# In your app's resources.py
from import_export import resources
from .models import StudentOnRoute, BusPayment

class StudentOnRouteResource(resources.ModelResource):
    class Meta:
        model = StudentOnRoute
        # Fields you want to include in the import/export file
        fields = ('id', 'student', 'route', 'session', 'term', 'is_active', 'created_at', 'updated')

class BusPaymentResource(resources.ModelResource):
    class Meta:
        model = BusPayment
        fields = ('id', 'enrollment', 'amount_paid', 'payment_method', 'payment_date', 'is_approved')