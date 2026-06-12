from django.core.management.base import BaseCommand
from results.models import Score


class Command(BaseCommand):
    help = "Populate standard field on Score records"

    def handle(self, *args, **options):

        updated = 0

        scores = Score.objects.filter(
            standard__isnull=True
        ).select_related(
            'student',
            'student__current_class'
        )

        for score in scores:

            if score.student.current_class:

                score.standard = score.student.current_class

                score.save(
                    update_fields=['standard']
                )

                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated} score records.'
            )
        )