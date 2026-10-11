from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from elearning.lessonnotes.forms import subject_standard_field
from elearning.lessonnotes.models import LessonNote


class Command(BaseCommand):
    help = ('Link lesson notes written BEFORE subjects became selectable to the matching '
            'curriculum.Subject (by name, and by class when subjects belong to classes). '
            'Run once after upgrading. Use --dry-run to preview.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        Subject = apps.get_model('curriculum', 'Subject')
        if not any(f.name == 'name' for f in Subject._meta.get_fields()):
            raise CommandError('curriculum.Subject has no "name" field, so notes cannot be matched by name.')
        class_field = subject_standard_field(Subject)

        linked = ambiguous = missing = 0
        for note in LessonNote.objects.filter(subject__isnull=True).select_related('standard'):
            matches = Subject.objects.filter(name__iexact=note.subject_name)
            if class_field:
                matches = matches.filter(**{class_field: note.standard})
            matches = list(matches[:2])
            if len(matches) == 1:
                linked += 1
                if not options['dry_run']:
                    LessonNote.objects.filter(pk=note.pk).update(subject=matches[0])
            elif matches:
                ambiguous += 1
            else:
                missing += 1
        prefix = '[dry run] ' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Linked {linked}; ambiguous (left as text) {ambiguous}; no matching subject {missing}.'))