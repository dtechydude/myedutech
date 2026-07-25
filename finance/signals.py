# finance/signals.py
"""
Keeps derived/denormalized state in sync automatically, so that any code
path that creates a Payment or Invoice (web form, admin, API, shell,
management command) behaves consistently without remembering to call
housekeeping functions manually.

Note: invoice_number/receipt_number assignment does NOT live here — it's
in Invoice.save()/Receipt.save() directly (see models.py), specifically so
numbering doesn't depend on this signals module being imported correctly.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Invoice, Payment, Receipt, InvoiceItem
from . import services


@receiver(post_save, sender=Payment)
def on_payment_saved(sender, instance, created, **kwargs):
    # Create the receipt as soon as a payment is completed. Receipt.save()
    # assigns its own receipt_number — nothing extra needed here.
    if instance.status == Payment.Status.COMPLETED:
        Receipt.objects.get_or_create(payment=instance, defaults={'generated_by': instance.recorded_by})

        if instance.invoice_id:
            services.sync_invoice_status(instance.invoice)

    services.sync_student_ledger(instance.student, instance.term, instance.session)


@receiver(post_delete, sender=Payment)
def on_payment_deleted(sender, instance, **kwargs):
    if instance.invoice_id:
        try:
            services.sync_invoice_status(instance.invoice)
        except Exception:
            pass
    services.sync_student_ledger(instance.student, instance.term, instance.session)


@receiver(post_save, sender=InvoiceItem)
@receiver(post_delete, sender=InvoiceItem)
def on_invoice_item_changed(sender, instance, **kwargs):
    invoice = instance.invoice
    services.sync_invoice_status(invoice)
    services.sync_student_ledger(invoice.student, invoice.term, invoice.session)
