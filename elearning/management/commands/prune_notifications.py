from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from elearning.notices.models import Notification


class Command(BaseCommand):
    help = 'Delete READ notifications older than N days (default 90). Run weekly.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['days'])
        deleted, _ = Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} read notification(s) older than {options["days"]} days.'))