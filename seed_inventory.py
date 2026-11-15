
from inventory.models import InventoryCategory, InventoryItem, StockMovement
from decimal import Decimal

print("Starting KwikSchools Inventory Demo Data...")

# -------------------------------------------------
# 1. INVENTORY ITEMS
# name, category, unit, cost, reorder, location,
# opening quantity
# -------------------------------------------------

inventory_data = [
    ("A4 Paper", "Stationery", "ream", "6500", 10, "Admin Store", 40),
    ("Blue Ballpoint Pen", "Stationery", "pcs", "150", 50, "Admin Store", 200),
    ("Exercise Books", "Stationery", "pcs", "450", 100, "Main Store", 300),
    ("Whiteboard Marker", "Stationery", "pcs", "500", 20, "Staff Room", 60),
    ("Stapler", "Stationery", "pcs", "2500", 5, "Admin Office", 15),

    ("Liquid Soap", "Cleaning Supplies", "litre", "2000", 10, "Cleaning Store", 30),
    ("Disinfectant", "Cleaning Supplies", "litre", "2500", 10, "Cleaning Store", 25),
    ("Brooms", "Cleaning Supplies", "pcs", "1200", 10, "Cleaning Store", 40),
    ("Mop", "Cleaning Supplies", "pcs", "2500", 5, "Cleaning Store", 15),
    ("Waste Bin", "Cleaning Supplies", "pcs", "4500", 5, "Classrooms Store", 20),

    ("Whiteboard", "Teaching Materials", "pcs", "25000", 3, "Classroom Store", 10),
    ("Mathematical Set", "Teaching Materials", "pcs", "1500", 20, "Academic Store", 50),
    ("Wall Map", "Teaching Materials", "pcs", "8000", 5, "Geography Room", 12),

    ("Desktop Computer", "ICT Equipment", "pcs", "450000", 2, "ICT Laboratory", 8),
    ("Keyboard", "ICT Equipment", "pcs", "12000", 5, "ICT Laboratory", 15),
    ("Computer Mouse", "ICT Equipment", "pcs", "7500", 5, "ICT Laboratory", 20),
    ("Projector", "ICT Equipment", "pcs", "350000", 1, "ICT Store", 4),

    ("Football", "Sports Equipment", "pcs", "15000", 5, "Sports Store", 12),
    ("Basketball", "Sports Equipment", "pcs", "18000", 3, "Sports Store", 8),

    ("Laboratory Gloves", "Science Laboratory", "box", "12000", 5, "Science Laboratory", 20),
]

# -------------------------------------------------
# 2. CREATE CATEGORIES AND ITEMS
# -------------------------------------------------

items = {}

for name, category_name, unit, cost, reorder, location, opening_qty in inventory_data:

    category, _ = InventoryCategory.objects.get_or_create(
        name=category_name
    )

    item, created = InventoryItem.objects.get_or_create(
        name=name,
        category=category,
        defaults={
            "unit": unit,
            "unit_cost": Decimal(cost),
            "reorder_level": reorder,
            "location": location,
            "quantity_in_stock": 0,
        }
    )

    items[name] = item

    # Opening stock is recorded through StockMovement,
    # so the model automatically updates quantity_in_stock.

    opening_marker = "KWIKSCHOOLS-DEMO:OPENING"

    if not item.movements.filter(notes__contains=opening_marker).exists():
        StockMovement.objects.create(
            item=item,
            movement_type="in",
            quantity=opening_qty,
            notes=(
                f"{opening_marker} - "
                f"Opening stock received for demonstration."
            )
        )

    print(f"Item processed: {name}")

# -------------------------------------------------
# 3. SAMPLE STOCK MOVEMENTS
# type: in, out, transfer, damaged
# -------------------------------------------------

movement_data = [
    # Stock issued to departments
    ("A4 Paper", "out", 8, "Admin Department", "", "Paper issued for office use."),
    ("Blue Ballpoint Pen", "out", 40, "Teaching Staff", "", "Pens distributed to teachers."),
    ("Exercise Books", "out", 100, "Primary Department", "", "Exercise books issued to pupils."),
    ("Whiteboard Marker", "out", 15, "Teaching Staff", "", "Markers distributed to teachers."),
    ("Liquid Soap", "out", 8, "Cleaning Department", "", "Soap issued for routine cleaning."),
    ("Disinfectant", "out", 5, "Cleaning Department", "", "Disinfectant issued for sanitation."),
    ("Brooms", "out", 12, "Classroom Department", "", "Brooms issued to classrooms."),
    ("Mop", "out", 5, "Cleaning Department", "", "Mops issued to cleaning staff."),
    ("Mathematical Set", "out", 30, "JSS Department", "", "Mathematical sets issued to students."),
    ("Football", "out", 5, "Sports Department", "", "Football issued for sports activities."),
    ("Basketball", "out", 2, "Sports Department", "", "Basketballs issued for training."),
    ("Laboratory Gloves", "out", 12, "Science Laboratory", "", "Gloves issued for practical lessons."),

    # Damaged or lost items
    ("Blue Ballpoint Pen", "damaged", 5, "", "", "Five pens declared damaged."),
    ("Whiteboard Marker", "damaged", 2, "", "", "Two markers found unusable."),

    # Internal transfers
    ("Desktop Computer", "transfer", 2, "ICT Department", "Computer Room 2",
     "Two computers transferred to Computer Room 2."),
    ("Whiteboard", "transfer", 2, "Academic Department", "JSS Classroom Block",
     "Whiteboards transferred to the JSS classroom block."),
]

# -------------------------------------------------
# 4. RECORD MOVEMENTS
# -------------------------------------------------

for index, movement in enumerate(movement_data, start=1):

    name, movement_type, quantity, issued_to, to_location, notes = movement

    item = items[name]

    marker = f"KWIKSCHOOLS-DEMO:MOVEMENT-{index}"

    # Prevent duplicate demo transactions when rerunning.
    if item.movements.filter(notes__contains=marker).exists():
        continue

    StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        issued_to=issued_to,
        to_location=to_location,
        notes=f"{marker} - {notes}"
    )

    print(f"Movement recorded: {name} - {movement_type} ({quantity})")

# -------------------------------------------------
# 5. SUMMARY
# -------------------------------------------------

print("\n===================================")
print("KWIKSCHOOLS INVENTORY DEMO CREATED")
print("===================================")

print("Categories:", InventoryCategory.objects.count())
print("Inventory items:", InventoryItem.objects.count())
print("Stock movements:", StockMovement.objects.count())

print("\nCURRENT INVENTORY SUMMARY")

for item in InventoryItem.objects.filter(name__in=items.keys()).order_by("name"):
    print(
        f"{item.name}: "
        f"{item.quantity_in_stock} {item.get_unit_display()} | "
        f"Location: {item.location} | "
        f"Low Stock: {item.is_low_stock}"
    )

print("\nInventory demo setup completed successfully.")
