import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import calculate_schedule, inventory_summary, material_requirements


NOW = "2026-02-17T09:00:00Z"


def po(po_number, product_type, quantity, order_date):
    return {
        "id": int(po_number.split("-")[-1]),
        "po_number": po_number,
        "customer_name": "Test Customer",
        "product_type": product_type,
        "quantity": quantity,
        "notes": "",
        "order_date": order_date,
        "created_at": order_date,
    }


def supply(material_type, quantity_kg, eta):
    return {
        "id": 1,
        "material_type": material_type,
        "quantity_kg": quantity_kg,
        "supplier_name": "Supplier",
        "tracking_number": f"TRK-{material_type}",
        "eta": eta,
        "order_date": eta,
        "created_at": eta,
    }


class SchedulerTest(unittest.TestCase):
    def test_material_requirements_are_calculated_from_business_rules(self):
        self.assertEqual(
            material_requirements("1-Liter Bottle", 1000),
            {"PET Resin": 20.0, "PTA": 15.0, "Ethylene Glycol": 10.0},
        )
        self.assertEqual(
            material_requirements("1-Gallon Bottle", 1000),
            {"PET Resin": 65.0, "PTA": 45.0, "Ethylene Glycol": 20.0},
        )

    def test_orders_are_assigned_to_dedicated_lines(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 2000, "2026-02-18T00:00:00Z"),
            po("PO-2026-0002", "1-Gallon Bottle", 1500, "2026-02-18T00:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 1000, "2026-02-01T00:00:00Z"),
            supply("PTA", 1000, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 1000, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        by_po = {order["po_number"]: order for order in result["orders_fifo"]}
        self.assertEqual(by_po["PO-2026-0001"]["production_line"], "1-Liter Production Line")
        self.assertEqual(by_po["PO-2026-0002"]["production_line"], "1-Gallon Production Line")

    def test_same_line_orders_follow_fifo_capacity(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 2000, "2026-02-18T00:00:00Z"),
            po("PO-2026-0002", "1-Liter Bottle", 2000, "2026-02-18T00:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 1000, "2026-02-01T00:00:00Z"),
            supply("PTA", 1000, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 1000, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        self.assertEqual(result["orders_fifo"][0]["expected_start"], "2026-02-18T00:00:00Z")
        self.assertEqual(result["orders_fifo"][1]["expected_start"], "2026-02-18T01:00:00Z")

    def test_different_lines_can_start_at_same_time(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 2000, "2026-02-18T00:00:00Z"),
            po("PO-2026-0002", "1-Gallon Bottle", 1500, "2026-02-18T00:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 1000, "2026-02-01T00:00:00Z"),
            supply("PTA", 1000, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 1000, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        starts = {order["po_number"]: order["expected_start"] for order in result["orders_fifo"]}
        self.assertEqual(starts["PO-2026-0001"], "2026-02-18T00:00:00Z")
        self.assertEqual(starts["PO-2026-0002"], "2026-02-18T00:00:00Z")

    def test_future_supply_creates_delay_expected(self):
        orders = [po("PO-2026-0001", "1-Gallon Bottle", 1000, "2026-02-18T00:00:00Z")]
        supplies = [
            supply("PET Resin", 65, "2026-02-20T00:00:00Z"),
            supply("PTA", 45, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 20, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        order = result["orders_fifo"][0]
        self.assertEqual(order["status"], "Delay expected")
        self.assertEqual(order["expected_start"], "2026-02-20T00:00:00Z")

    def test_missing_total_supply_is_unable_to_fulfill(self):
        orders = [po("PO-2026-0001", "1-Gallon Bottle", 1000, "2026-02-18T00:00:00Z")]
        supplies = [
            supply("PET Resin", 1, "2026-02-01T00:00:00Z"),
            supply("PTA", 45, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 20, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        self.assertEqual(result["orders_fifo"][0]["status"], "Unable to fulfill")
        self.assertIsNone(result["orders_fifo"][0]["expected_completion"])

    def test_material_consumption_can_block_later_fifo_order(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 1000, "2026-02-18T00:00:00Z"),
            po("PO-2026-0002", "1-Liter Bottle", 1000, "2026-02-18T01:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 20, "2026-02-01T00:00:00Z"),
            supply("PTA", 15, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 10, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        self.assertEqual(result["orders_fifo"][0]["status"], "Pending")
        self.assertEqual(result["orders_fifo"][1]["status"], "Unable to fulfill")

    def test_status_transitions_around_planning_time(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 2000, "2026-02-17T07:00:00Z"),
            po("PO-2026-0002", "1-Liter Bottle", 2000, "2026-02-17T09:00:00Z"),
            po("PO-2026-0003", "1-Liter Bottle", 2000, "2026-02-17T11:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 1000, "2026-02-01T00:00:00Z"),
            supply("PTA", 1000, "2026-02-01T00:00:00Z"),
            supply("Ethylene Glycol", 1000, "2026-02-01T00:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        statuses = [order["status"] for order in result["orders_fifo"]]
        self.assertEqual(statuses, ["Completed", "In Production", "Pending"])

    def test_inventory_summary_respects_planning_time_without_schedule(self):
        supplies = [
            supply("PET Resin", 10, "2026-02-17T08:00:00Z"),
            supply("PET Resin", 20, "2026-02-17T10:00:00Z"),
            supply("PTA", 5, "2026-02-17T08:00:00Z"),
            supply("Ethylene Glycol", 7, "2026-02-17T10:00:00Z"),
        ]
        summary = inventory_summary(supplies)
        by_material = {item["material_type"]: item for item in summary}
        self.assertEqual(by_material["PET Resin"]["on_hand_kg"], 10.0)
        self.assertEqual(by_material["PET Resin"]["incoming_kg"], 20.0)
        self.assertEqual(by_material["PTA"]["on_hand_kg"], 5.0)
        self.assertEqual(by_material["Ethylene Glycol"]["incoming_kg"], 7.0)

    def test_inventory_summary_subtracts_started_order_materials(self):
        orders = [
            po("PO-2026-0001", "1-Liter Bottle", 1000, "2026-02-17T08:00:00Z"),
        ]
        supplies = [
            supply("PET Resin", 30, "2026-02-17T07:00:00Z"),
            supply("PTA", 20, "2026-02-17T07:00:00Z"),
            supply("Ethylene Glycol", 15, "2026-02-17T07:00:00Z"),
        ]
        result = calculate_schedule(orders, supplies, NOW)
        by_material = {item["material_type"]: item for item in result["inventory"]}
        self.assertEqual(by_material["PET Resin"]["on_hand_kg"], 10.0)
        self.assertEqual(by_material["PTA"]["on_hand_kg"], 5.0)
        self.assertEqual(by_material["Ethylene Glycol"]["on_hand_kg"], 5.0)


if __name__ == "__main__":
    unittest.main()
