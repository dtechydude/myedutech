# students/context_processors.py

def student_context(request):
    student = None
    if request.user.is_authenticated and hasattr(request.user, 'student'):
        student = request.user.student
    return {'student': student}