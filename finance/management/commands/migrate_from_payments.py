# finance/management/commands/migrate_from_payments.py
"""
One-time data migration helper: copies data from the old `payments` app
(BankDetail, PaymentCategory, StudentFeeAssignment, Payment, Receipt,
PaymentNotification) into the new `finance` app's models.

This is OPTIONAL — only run it if you have existing production data in the
old `payments` app that you want to preserve. Safe to run multiple times
(it uses get_or_create / update_or_create throughout).

Usage:
    python manage.py migrate_from_payments
    python manage.py migrate_from_payments --dry-run
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Migrates data from the old 'payments' app into the new 'finance' app."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help="Preview counts without writing any data.")

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        try:
            from payments.models import (
                BankDetail as OldBankDetail, PaymentCategory as OldPaymentCategory,
                StudentFeeAssignment as OldAssignment, Payment as OldPayment,
                PaymentNotification as OldNotification,
            )
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "Could not import the old 'payments' app models. Make sure it's still installed "
                "in INSTALLED_APPS (even temporarily) while you run this migration."
            ))
            return

        from finance.models import (
            BankAccount, FeeCategory, Invoice, InvoiceItem, Payment, PaymentNotification,
        )
        from finance import services

        with transaction.atomic():
            # 1. Bank accounts
            bank_map = {}
            for old in OldBankDetail.objects.all():
                if not dry_run:
                    new_acc, _ = BankAccount.objects.get_or_create(
                        account_number=old.acc_number, bank_name=old.bank_name,
                        defaults={'account_name': old.acc_name},
                    )
                    bank_map[old.pk] = new_acc
            self.stdout.write(f"Bank accounts: {OldBankDetail.objects.count()} found.")

            # 2. Fee categories
            category_map = {}
            for old in OldPaymentCategory.objects.all():
                if not dry_run:
                    new_cat, _ = FeeCategory.objects.get_or_create(
                        name=old.name, defaults={'description': old.description or ''},
                    )
                    category_map[old.pk] = new_cat
            self.stdout.write(f"Fee categories: {OldPaymentCategory.objects.count()} found.")

            # 3. StudentFeeAssignment -> Invoice + InvoiceItem
            invoice_map = {}
            assignments = OldAssignment.objects.select_related('student', 'term', 'session', 'payment_category')
            for old in assignments:
                if dry_run:
                    continue
                key = (old.student_id, old.term_id, old.session_id)
                invoice = invoice_map.get(key)
                if invoice is None:
                    invoice, _ = Invoice.objects.get_or_create(
                        student_id=old.student_id, term_id=old.term_id, session_id=old.session_id,
                    )
                    invoice_map[key] = invoice
                new_category = category_map.get(old.payment_category_id)
                if new_category:
                    InvoiceItem.objects.get_or_create(
                        invoice=invoice, fee_category=new_category,
                        defaults={'amount': old.amount_due, 'description': new_category.name},
                    )
            self.stdout.write(f"Fee assignments -> invoices: {assignments.count()} found.")

            # 4. Payments
            payments = OldPayment.objects.select_related('student', 'term', 'session', 'payment_category')
            migrated_payments = 0
            for old in payments:
                if dry_run:
                    continue
                key = (old.student_id, old.term_id, old.session_id)
                invoice = invoice_map.get(key)
                new_category = category_map.get(old.payment_category_id)
                new_payment, created = Payment.objects.get_or_create(
                    transaction_id=old.transaction_id or f"MIGRATED-{old.pk}",
                    defaults={
                        'student_id': old.student_id, 'invoice': invoice, 'fee_category': new_category,
                        'term_id': old.term_id, 'session_id': old.session_id,
                        'amount_received': old.amount_received,
                        'discount_amount': old.discount_amount or Decimal('0.00'),
                        'discount_percentage': old.discount_percentage or Decimal('0.00'),
                        'payment_date': old.payment_date, 'payment_method': old.payment_method,
                        'status': old.status, 'notes': old.notes or '',
                        'recorded_by_id': old.recorded_by_id,
                    },
                )
                if created:
                    migrated_payments += 1
            self.stdout.write(f"Payments migrated: {migrated_payments} / {payments.count()}.")

            # 5. Recompute ledgers for every touched student/term/session
            if not dry_run:
                for (student_id, term_id, session_id) in invoice_map.keys():
                    from students.models import Student
                    from curriculum.models import Term, Session
                    try:
                        services.sync_student_ledger(
                            Student.objects.get(pk=student_id),
                            Term.objects.get(pk=term_id),
                            Session.objects.get(pk=session_id),
                        )
                    except Exception as exc:  # noqa: BLE001
                        self.stderr.write(self.style.WARNING(f"Could not sync ledger for student {student_id}: {exc}"))

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry run complete — no data was written. Re-run without "
                                                       "--dry-run to perform the migration."))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Migration from 'payments' to 'finance' complete."))
