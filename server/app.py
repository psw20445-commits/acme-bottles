from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from db import connect, initialize_database, next_po_number, rows_to_dicts
from scheduler import MATERIALS, PLANNING_NOW, PRODUCTS, calculate_schedule, parse_datetime
from seed import seed


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
DEFAULT_PORT = 8000


def planning_now() -> str:
    return os.environ.get("ACME_PLANNING_NOW", PLANNING_NOW)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AcmeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api_get(parsed)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            if parsed.path == "/api/purchase-orders":
                self.create_purchase_order(payload)
            elif parsed.path == "/api/supplies":
                self.create_supply_order(payload)
            elif parsed.path == "/api/reset":
                seed(force=True)
                self.send_json({"ok": True})
            else:
                self.send_error(404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except Exception:
            self.send_json({"error": "Unexpected server error"}, status=500)

    def handle_api_get(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/purchase-orders":
            self.send_json({"purchase_orders": self.purchase_orders(reverse=True)})
        elif parsed.path == "/api/supplies":
            supply_orders = self.supply_orders()
            self.send_json(
                {
                    "supply_orders": list(reversed(supply_orders)),
                    "inventory": calculate_schedule(self.purchase_orders(), supply_orders, planning_now())["inventory"],
                }
            )
        elif parsed.path == "/api/production-status":
            now = query.get("now", [planning_now()])[0]
            self.send_json(calculate_schedule(self.purchase_orders(), self.supply_orders(), now))
        elif parsed.path == "/api/meta":
            self.send_json({"products": list(PRODUCTS.keys()), "materials": list(MATERIALS), "planning_now": planning_now()})
        else:
            self.send_error(404)

    def purchase_orders(self, reverse: bool = False) -> list[dict]:
        order = "DESC" if reverse else "ASC"
        with connect() as db:
            return rows_to_dicts(
                db.execute(
                    f"SELECT * FROM purchase_orders ORDER BY order_date {order}, id {order}"
                ).fetchall()
            )

    def supply_orders(self, reverse: bool = False) -> list[dict]:
        order = "DESC" if reverse else "ASC"
        with connect() as db:
            return rows_to_dicts(
                db.execute(
                    f"SELECT * FROM supply_orders ORDER BY order_date {order}, id {order}"
                ).fetchall()
            )

    def create_purchase_order(self, payload: dict) -> None:
        customer_name = require_text(payload, "customer_name")
        product_type = require_choice(payload, "product_type", PRODUCTS.keys())
        quantity = require_positive_int(payload, "quantity")
        notes = str(payload.get("notes", "")).strip()
        order_date = str(payload.get("order_date") or utc_now())
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            po_number = next_po_number(db, parse_datetime(order_date).year)
            db.execute(
                """
                INSERT INTO purchase_orders
                    (po_number, customer_name, product_type, quantity, notes, order_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (po_number, customer_name, product_type, quantity, notes, order_date),
            )
            db.commit()
        self.send_json({"ok": True, "po_number": po_number}, status=201)

    def create_supply_order(self, payload: dict) -> None:
        material_type = require_choice(payload, "material_type", MATERIALS)
        quantity_kg = require_positive_float(payload, "quantity_kg")
        supplier_name = str(payload.get("supplier_name", "")).strip()
        tracking_number = require_text(payload, "tracking_number")
        eta = require_text(payload, "eta")
        order_date = str(payload.get("order_date") or utc_now())
        with connect() as db:
            db.execute(
                """
                INSERT INTO supply_orders
                    (material_type, quantity_kg, supplier_name, tracking_number, eta, order_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (material_type, quantity_kg, supplier_name, tracking_number, eta, order_date),
            )
            db.commit()
        self.send_json({"ok": True}, status=201)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def require_text(payload: dict, key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def require_choice(payload: dict, key: str, choices) -> str:
    value = require_text(payload, key)
    if value not in choices:
        raise ValueError(f"{key} must be one of: {', '.join(choices)}")
    return value


def require_positive_int(payload: dict, key: str) -> int:
    try:
        value = int(payload.get(key))
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a positive integer")
    if value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def require_positive_float(payload: dict, key: str) -> float:
    try:
        value = float(payload.get(key))
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a positive number")
    if value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return value


def main() -> None:
    initialize_database()
    seed()
    port = int(os.environ.get("ACME_PORT", DEFAULT_PORT))
    server = ThreadingHTTPServer(("127.0.0.1", port), AcmeHandler)
    print(f"ACME Bottles running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
