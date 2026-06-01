from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any


PLANNING_NOW = "2026-02-17T09:00:00Z"

PRODUCTS = {
    "1-Liter Bottle": {
        "line": "1-Liter Production Line",
        "capacity_per_hour": 2000,
        "materials_g": {
            "PET Resin": 20,
            "PTA": 15,
            "Ethylene Glycol": 10,
        },
    },
    "1-Gallon Bottle": {
        "line": "1-Gallon Production Line",
        "capacity_per_hour": 1500,
        "materials_g": {
            "PET Resin": 65,
            "PTA": 45,
            "Ethylene Glycol": 20,
        },
    },
}

MATERIALS = ("PET Resin", "PTA", "Ethylene Glycol")


@dataclass(frozen=True)
class SupplyLot:
    material_type: str
    quantity_kg: float
    available_at: datetime


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.fromisoformat(PLANNING_NOW.replace("Z", "+00:00"))
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def material_requirements(product_type: str, quantity: int) -> dict[str, float]:
    product = PRODUCTS[product_type]
    return {
        material: grams_per_unit * quantity / 1000
        for material, grams_per_unit in product["materials_g"].items()
    }


def production_duration(product_type: str, quantity: int) -> timedelta:
    product = PRODUCTS[product_type]
    hours = quantity / product["capacity_per_hour"]
    seconds = ceil(hours * 3600)
    return timedelta(seconds=seconds)


def _build_supply_lots(supply_orders: list[dict[str, Any]]) -> dict[str, list[SupplyLot]]:
    lots: dict[str, list[SupplyLot]] = {material: [] for material in MATERIALS}
    for supply in supply_orders:
        material = supply["material_type"]
        if material not in lots:
            continue
        lots[material].append(
            SupplyLot(
                material_type=material,
                quantity_kg=float(supply["quantity_kg"]),
                available_at=parse_datetime(supply.get("eta")),
            )
        )
    for material in lots:
        lots[material].sort(key=lambda lot: lot.available_at)
    return lots


def _available_by(
    lots: dict[str, list[SupplyLot]],
    consumed: dict[str, float],
    requirements: dict[str, float],
    at_time: datetime,
) -> bool:
    for material, required_kg in requirements.items():
        supply_kg = sum(
            lot.quantity_kg for lot in lots[material] if lot.available_at <= at_time
        )
        if supply_kg - consumed[material] + 1e-9 < required_kg:
            return False
    return True


def _total_supply_can_cover(
    lots: dict[str, list[SupplyLot]],
    consumed: dict[str, float],
    requirements: dict[str, float],
) -> bool:
    for material, required_kg in requirements.items():
        total_kg = sum(lot.quantity_kg for lot in lots[material])
        if total_kg - consumed[material] + 1e-9 < required_kg:
            return False
    return True


def _earliest_material_time(
    lots: dict[str, list[SupplyLot]],
    consumed: dict[str, float],
    requirements: dict[str, float],
    earliest_start: datetime,
) -> datetime | None:
    if not _total_supply_can_cover(lots, consumed, requirements):
        return None
    candidate_times = {earliest_start}
    for material_lots in lots.values():
        candidate_times.update(lot.available_at for lot in material_lots if lot.available_at >= earliest_start)
    for candidate in sorted(candidate_times):
        if _available_by(lots, consumed, requirements, candidate):
            return candidate
    return None


def calculate_schedule(
    purchase_orders: list[dict[str, Any]],
    supply_orders: list[dict[str, Any]],
    now_value: str = PLANNING_NOW,
) -> dict[str, Any]:
    now = parse_datetime(now_value)
    lots = _build_supply_lots(supply_orders)
    consumed = {material: 0.0 for material in MATERIALS}
    line_available: dict[str, datetime] = {}
    scheduled: list[dict[str, Any]] = []

    fifo_orders = sorted(
        purchase_orders,
        key=lambda order: (parse_datetime(order["order_date"]), order.get("id", 0)),
    )

    for order in fifo_orders:
        product_type = order["product_type"]
        product = PRODUCTS[product_type]
        line = product["line"]
        order_date = parse_datetime(order["order_date"])
        base_start = max(order_date, line_available.get(line, order_date))
        requirements = material_requirements(product_type, int(order["quantity"]))
        material_ready_at = _earliest_material_time(lots, consumed, requirements, base_start)

        if material_ready_at is None:
            scheduled.append(
                _scheduled_order(order, line, requirements, None, None, "Unable to fulfill", now, base_start)
            )
            continue

        start_at = max(base_start, material_ready_at)
        completion_at = start_at + production_duration(product_type, int(order["quantity"]))
        for material, required_kg in requirements.items():
            consumed[material] += required_kg
        line_available[line] = completion_at

        if completion_at <= now:
            status = "Completed"
        elif start_at <= now < completion_at:
            status = "In Production"
        elif material_ready_at > base_start:
            status = "Delay expected"
        else:
            status = "Pending"

        scheduled.append(
            _scheduled_order(order, line, requirements, start_at, completion_at, status, now, base_start)
        )

    in_production = []
    for line in ("1-Liter Production Line", "1-Gallon Production Line"):
        current = next(
            (order for order in scheduled if order["production_line"] == line and order["status"] == "In Production"),
            None,
        )
        in_production.append(
            {
                "line": line,
                "order": current,
            }
        )

    return {
        "planning_now": isoformat(now),
        "in_production": in_production,
        "orders_fifo": scheduled,
        "inventory": inventory_summary(supply_orders, now, scheduled),
    }


def _scheduled_order(
    order: dict[str, Any],
    line: str,
    requirements: dict[str, float],
    start_at: datetime | None,
    completion_at: datetime | None,
    status: str,
    now: datetime,
    base_start: datetime,
) -> dict[str, Any]:
    delay_hours = None
    if start_at and start_at > base_start:
        delay_hours = round((start_at - base_start).total_seconds() / 3600, 2)
    return {
        **order,
        "production_line": line,
        "required_materials_kg": {key: round(value, 3) for key, value in requirements.items()},
        "expected_start": isoformat(start_at),
        "expected_completion": isoformat(completion_at),
        "status": status,
        "delay_hours": delay_hours,
        "is_late": bool(completion_at and completion_at < now and status != "Completed"),
    }


def inventory_summary(
    supply_orders: list[dict[str, Any]],
    now: datetime | None = None,
    scheduled_orders: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if now is None:
        now = parse_datetime(PLANNING_NOW)
    consumed = {material: 0.0 for material in MATERIALS}
    for order in scheduled_orders or []:
        expected_start = order.get("expected_start")
        if not expected_start or parse_datetime(expected_start) > now:
            continue
        if order.get("status") == "Unable to fulfill":
            continue
        for material, required_kg in order.get("required_materials_kg", {}).items():
            if material in consumed:
                consumed[material] += float(required_kg)

    summary = []
    for material in MATERIALS:
        orders = [supply for supply in supply_orders if supply["material_type"] == material]
        received = sum(
            float(supply["quantity_kg"])
            for supply in orders
            if parse_datetime(supply.get("eta")) <= now
        )
        on_hand = max(0.0, received - consumed[material])
        incoming = sum(
            float(supply["quantity_kg"])
            for supply in orders
            if parse_datetime(supply.get("eta")) > now
        )
        summary.append(
            {
                "material_type": material,
                "on_hand_kg": round(on_hand, 3),
                "incoming_kg": round(incoming, 3),
                "order_count": len(orders),
                "incoming_count": sum(1 for supply in orders if parse_datetime(supply.get("eta")) > now),
            }
        )
    return summary
