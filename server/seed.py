from __future__ import annotations

from db import connect, initialize_database


PURCHASE_ORDERS = [
    ("PO-2026-0001", "AquaPure Beverages", "1-Liter Bottle", 50000, "Initial water bottle run", "2026-01-05T08:00:00Z"),
    ("PO-2026-0002", "GreenLeaf Naturals", "1-Liter Bottle", 30000, "Retail restock", "2026-01-12T08:00:00Z"),
    ("PO-2026-0003", "FreshField Dairy", "1-Gallon Bottle", 75000, "Bulk dairy packaging", "2026-01-20T08:00:00Z"),
    ("PO-2026-0004", "SunSip Beverages", "1-Liter Bottle", 100000, "Spring promotion", "2026-02-01T08:00:00Z"),
    ("PO-2026-0005", "ClearSpring Water Co.", "1-Gallon Bottle", 60000, "Pending warehouse launch", "2026-02-10T08:00:00Z"),
    ("PO-2026-0006", "NorthStar Foods", "1-Gallon Bottle", 100000, "Blocked by depleted PTA supply", "2026-02-14T08:00:00Z"),
]

SUPPLY_ORDERS = [
    ("PET Resin", 5000, "Global Resin Co.", "TRK-PET-001", "2026-01-03T06:00:00Z", "2026-01-03T06:00:00Z"),
    ("PTA", 4000, "AcidWorks Supply", "TRK-PTA-001", "2026-01-03T06:00:00Z", "2026-01-03T06:00:00Z"),
    ("Ethylene Glycol", 1200, "Glycol Partners", "TRK-EG-001", "2026-01-03T06:00:00Z", "2026-01-03T06:00:00Z"),
    ("PET Resin", 7000, "Global Resin Co.", "TRK-PET-002", "2026-01-18T06:00:00Z", "2026-01-18T06:00:00Z"),
    ("PTA", 3000, "AcidWorks Supply", "TRK-PTA-002", "2026-01-25T06:00:00Z", "2026-01-25T06:00:00Z"),
    ("PET Resin", 7000, "Pacific Polymer", "TRK-PET-003", "2026-02-23T06:00:00Z", "2026-02-08T06:00:00Z"),
    ("Ethylene Glycol", 2500, "Glycol Partners", "TRK-EG-002", "2026-02-15T08:00:00Z", "2026-02-08T06:00:00Z"),
    ("Ethylene Glycol", 1000, "Glycol Partners", "TRK-EG-003", "2026-02-24T06:00:00Z", "2026-02-12T06:00:00Z"),
    ("PTA", 3000, "AcidWorks Supply", "TRK-PTA-003", "2026-02-25T06:00:00Z", "2026-02-12T06:00:00Z"),
]


def seed(force: bool = False) -> None:
    initialize_database()
    with connect() as db:
        if force:
            db.execute("DELETE FROM purchase_orders")
            db.execute("DELETE FROM supply_orders")
        existing = db.execute("SELECT COUNT(*) AS count FROM purchase_orders").fetchone()
        if existing["count"]:
            return
        db.executemany(
            """
            INSERT INTO purchase_orders
                (po_number, customer_name, product_type, quantity, notes, order_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            PURCHASE_ORDERS,
        )
        db.executemany(
            """
            INSERT INTO supply_orders
                (material_type, quantity_kg, supplier_name, tracking_number, eta, order_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            SUPPLY_ORDERS,
        )
        db.commit()


if __name__ == "__main__":
    seed(force=True)
    print("Seeded ACME Bottles database.")
