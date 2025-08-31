from curriculum.models import SchoolIdentity  # Replace 'your_app' with the app name where SchoolIdentity is located

def school_identity(request):
    try:
        school_info = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_info = None

    return {'school_info': school_info}