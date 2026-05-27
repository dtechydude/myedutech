"""
management/commands/import_students.py
KwikSchools — Smarter Schools!

CLI management command for bulk importing students from a CSV file.

Usage:
    python manage.py import_students path/to/students.csv
    python manage.py import_students path/to/students.csv --overwrite
    python manage.py import_students path/to/students.csv --dry-run
"""

import os
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Bulk import students from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the CSV file.')
        parser.add_argument(
            '--overwrite',
            action='store_true',
            default=False,
            help='Update existing students (matched by USN) instead of skipping them.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Parse and validate the CSV without saving anything to the database.',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        overwrite = options['overwrite']
        dry_run   = options['dry_run']

        if not os.path.isfile(csv_path):
            raise CommandError(f'File not found: {csv_path}')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY-RUN mode — no data will be saved.'))

        self.stdout.write(f'Reading: {csv_path}')

        try:
            from students.services import process_student_csv

            if dry_run:
                # For dry-run, monkey-patch transaction.atomic to be a no-op
                # by wrapping process_student_csv with a manual rollback.
                from django.db import transaction

                with transaction.atomic():
                    with open(csv_path, 'rb') as f:
                        results = process_student_csv(f, overwrite=overwrite)
                    transaction.set_rollback(True)  # Roll back everything
            else:
                with open(csv_path, 'rb') as f:
                    results = process_student_csv(f, overwrite=overwrite)

        except Exception as e:
            raise CommandError(f'Import failed: {e}')

        # ── Summary ──────────────────────────────────────────────────────────
        mode = '[DRY-RUN] ' if dry_run else ''

        self.stdout.write(
            self.style.SUCCESS(
                f'\n{mode}Import complete:\n'
                f'  Total rows : {results["total_rows"]}\n'
                f'  Created    : {results["created"]}\n'
                f'  Updated    : {results["updated"]}\n'
                f'  Skipped    : {results["skipped"]}\n'
            )
        )

        if results['errors']:
            self.stdout.write(self.style.WARNING(f'\n{len(results["errors"])} issue(s) found:\n'))
            for err in results['errors']:
                self.stdout.write(f'  ⚠  {err}')
        else:
            self.stdout.write(self.style.SUCCESS('No errors detected.'))
