from django.core.management.base import BaseCommand

from staff.models import Teacher


class Command(BaseCommand):
    help = ('ONE-TIME step before using teacher status. Teacher.active used to default to False, so '
            'teachers already working at the school may be flagged inactive. This marks every teacher '
            'whose login currently works as ACTIVE. Teachers without a login, or with a disabled login, '
            'are left alone. It never changes any login. Use --dry-run first.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would change, change nothing.')

    def handle(self, *args, **options):
        todo = Teacher.objects.filter(active=False, user__isnull=False, user__is_active=True).select_related('user')
        no_login = Teacher.objects.filter(active=False, user__isnull=True).count()
        disabled = Teacher.objects.filter(active=False, user__isnull=False, user__is_active=False).count()

        ids = []
        for teacher in todo:
            ids.append(teacher.pk)
            self.stdout.write(f'  {teacher.display_name} ({teacher.user.get_username()})')
        if ids and not options['dry_run']:
            # .update() on purpose: no signals, so no logins are touched and nothing is logged as a status change
            Teacher.objects.filter(pk__in=ids).update(active=True)

        prefix = '[dry run] Would mark' if options['dry_run'] else 'Marked'
        self.stdout.write(self.style.SUCCESS(
            f'{prefix} {len(ids)} teacher(s) as active. Left as inactive: {disabled} with a disabled login, '
            f'{no_login} with no login at all. Review them in the Teacher Archive.'))