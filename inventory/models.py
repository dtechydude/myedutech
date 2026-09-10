from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from django.urls import reverse
from django.utils import timezone


class InventoryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Inventory Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


# class Vendor(models.Model):
#     name = models.CharField(max_length=150)
#     phone = models.CharField(max_length=20, blank=True)
#     address = models.CharField(max_length=200, blank=True)

#     def __str__(self):
#         return self.name


class InventoryItem(models.Model):
    UNIT_CHOICES = [
        ('pcs', 'Pieces'),
        ('box', 'Box'),
        ('set', 'Set'),
        ('carton', 'Carton'),
        ('litre', 'Litre'),
        ('kg', 'Kilogram'),
        ('ream', 'Ream'),
    ]

    name = models.CharField(max_length=150)
    category = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, related_name='items')
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')

    quantity_in_stock = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(
        default=5,
        help_text="Alert triggers when stock falls to or below this number."
    )

    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    location = models.CharField(max_length=100, blank=True, help_text="e.g. Store Room, Science Lab, Library")
    # ── QR tracking (additive) ──────────────────────────────────────
    qr_uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_asset = models.BooleanField(
        default=False,
        help_text="Tick for trackable individual assets (laptops, projectors) that get issued to a specific person, as opposed to bulk consumables (paper, chalk)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.quantity_in_stock} {self.get_unit_display()})"

    @property
    def total_value(self):
        return self.quantity_in_stock * self.unit_cost

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.reorder_level

    def get_qr_scan_url(self):
        """Public URL encoded into the printed QR label."""
        return reverse('inventory:scan_detail', kwargs={'qr_uid': self.qr_uid})

    @property
    def current_custody(self):
        """The active (not yet returned) custody record, if any."""
        return self.custody_records.filter(returned_date__isnull=True).order_by('-issued_date').first()




# class StockMovement(models.Model):
#     """
#     Every stock-in (purchase/donation) or stock-out (issue/damage/loss)
#     is logged here. quantity_in_stock on InventoryItem is always derived
#     from this ledger via save() — never edited directly — so stock levels
#     can't drift out of sync with the movement history.
#     """
#     MOVEMENT_TYPES = [
#         ('in', 'Stock In (Purchase/Donation)'),
#         ('out', 'Stock Out (Issued/Used)'),
#         ('damaged', 'Damaged/Lost'),
#         ('adjustment', 'Manual Adjustment'),
#     ]

#     item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
#     movement_type = models.CharField(max_length=15, choices=MOVEMENT_TYPES)
#     quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

#     vendor = models.ForeignKey(
#     'finance.Vendor', on_delete=models.SET_NULL, null=True, blank=True,
#     help_text="Only relevant for 'Stock In' — who the item was purchased from."
# )
#     issued_to = models.CharField(max_length=150, blank=True, help_text="e.g. Class name, department, staff name")
#     notes = models.TextField(blank=True)

#     recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#     date = models.DateField(auto_now_add=True)

#     class Meta:
#         ordering = ['-date', '-id']

#     def __str__(self):
#         return f"{self.get_movement_type_display()} — {self.item.name} ({self.quantity})"

#     def save(self, *args, **kwargs):
#         is_new = self.pk is None
#         super().save(*args, **kwargs)
#         if is_new:
#             self._apply_to_stock()

#     def _apply_to_stock(self):
#         item = self.item
#         if self.movement_type == 'in':
#             item.quantity_in_stock += self.quantity
#         elif self.movement_type in ('out', 'damaged'):
#             item.quantity_in_stock = max(item.quantity_in_stock - self.quantity, 0)
#         elif self.movement_type == 'adjustment':
#             item.quantity_in_stock = self.quantity  # treated as a manual reset to this exact figure
#         item.save(update_fields=['quantity_in_stock', 'updated_at'])

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In (Purchase/Donation)'),
        ('out', 'Stock Out (Used/Consumed)'),
        ('transfer', 'Internal Transfer (Location/Personnel)'),
        ('damaged', 'Damaged/Lost'),
        ('adjustment', 'Manual Adjustment'),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=15, choices=MOVEMENT_TYPES)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    vendor = models.ForeignKey(
        'finance.Vendor', on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Only for 'Stock In' — who the item was purchased from."
    )
    issued_to = models.CharField(
        max_length=150, blank=True,
        help_text="Person/department this movement concerns — e.g. 'Mrs. Bello', 'JSS2 Science Lab'."
    )
    to_location = models.CharField(
        max_length=150, blank=True,
        help_text="For 'Internal Transfer' — the item's new location. Updates the item's recorded location."
    )
    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.item.name} ({self.quantity})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self._apply_to_stock()

    def _apply_to_stock(self):
        item = self.item
        if self.movement_type == 'in':
            item.quantity_in_stock += self.quantity
        elif self.movement_type in ('out', 'damaged'):
            item.quantity_in_stock = max(item.quantity_in_stock - self.quantity, 0)
        elif self.movement_type == 'adjustment':
            item.quantity_in_stock = self.quantity
        elif self.movement_type == 'transfer' and self.to_location:
            item.location = self.to_location
        item.save(update_fields=['quantity_in_stock', 'location', 'updated_at'])

        

class ItemCustody(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='custody_records')

    held_by_name = models.CharField(
        max_length=150,
        help_text="Person responsible — staff, student, or department name."
    )
    assigned_location = models.CharField(
        max_length=150, blank=True,
        help_text="Where the item currently sits — e.g. 'Basic 3 Classroom', 'Science Lab', 'Admin Office'. Leave blank if it moves with the person (e.g. a phone)."
    )
    held_by_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='items_in_custody'
    )

    issued_date = models.DateField(default=timezone.now)
    expected_return_date = models.DateField(null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)

    issue_notes = models.TextField(blank=True)
    return_notes = models.TextField(blank=True)

    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='items_issued')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='items_received_back')

    class Meta:
        ordering = ['-issued_date']
        verbose_name_plural = "Item Custody Records"

    def __str__(self):
        status = "Returned" if self.returned_date else f"With {self.held_by_name}"
        if self.assigned_location:
            status += f" @ {self.assigned_location}"
        return f"{self.item.name} — {status}"

    @property
    def is_active(self):
        return self.returned_date is None

    @property
    def is_overdue(self):
        return self.is_active and self.expected_return_date is not None and self.expected_return_date < timezone.now().date()