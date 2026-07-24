# finance/management/commands/sync_finance_ledgers.py
"""
Recomputes every StudentAccountLedger and Invoice status from scratch.

Useful after a bulk data import/migration, or if you ever suspect the
cached ledger balances have drifted from the underlying Invoice/Payment
records. Safe to run any time — it's a pure recalculation, not a mutation
of source data.

Usage:
    python manage.py sync_finance_ledgers
"""
from django.core.management.base import BaseCommand

from finance.models import Invoice
from finance import services


class Command(BaseCommand):
    help = "Recalculates all student ledgers and invoice statuses from source Invoice/Payment records."

    def handle(self, *args, **options):
        invoices = Invoice.objects.select_related('student', 'term', 'session')
        seen = set()
        count = 0

        for invoice in invoices:
            services.sync_invoice_status(invoice)
            key = (invoice.student_id, invoice.term_id, invoice.session_id)
            if key not in seen:
                services.sync_student_ledger(invoice.student, invoice.term, invoice.session)
                seen.add(key)
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Synced {invoices.count()} invoice(s) and {count} student ledger(s)."
        ))
