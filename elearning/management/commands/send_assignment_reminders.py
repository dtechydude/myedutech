from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from elearning.models import Assignment
from elearning.notices import services
from elearning.notices.models import Notification
from elearning.notices.signals import lesson_url


class Command(BaseCommand):
    help = ('Remind students who have NOT yet submitted an assignment that is due soon. '
            'Run once a day (a scheduled task); it never notifies the same student twice.')

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=24, help='Remind for assignments due within N hours.')

    def handle(self, *args, **options):
        now = timezone.now()
        due_soon = (Assignment.objects.select_related('lesson__standard', 'lesson__subject')
                    .filter(due_date__gt=now, due_date__lte=now + timedelta(hours=options['hours'])))
        sent = 0
        for a in due_soon:
            pending = services.students_of_class(a.lesson.standard).exclude(
                student__assignment_submissions__assignment=a)
            sent += services.notify(
                pending, Notification.Category.ASSIGNMENT, f'Due soon: {a.title}',
                f'{a.lesson.subject.name} · due {timezone.localtime(a.due_date):%a, %b %d at %I:%M %p}',
                url=lesson_url(a.lesson) + '#homework-section', dedupe_key=f'due-soon-{a.pk}')
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminder(s) for {due_soon.count()} assignment(s).'))