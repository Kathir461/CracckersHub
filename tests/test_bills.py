import importlib
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import database

with patch.object(database, "init_db"):
    shop = importlib.import_module("app")


class BillTests(unittest.TestCase):
    def setUp(self):
        shop.app.config.update(TESTING=True, SECRET_KEY="bill-tests")
        self.client = shop.app.test_client()
        self.order = {
            "id": 42,
            "customer_name": "A Customer",
            "phone": "9876543210",
            "email": "customer@example.com",
            "address": "12 Festival Street",
            "total_amount": Decimal("350.00"),
            "payment_method": "gpay",
            "payment_status": "Paid",
            "created_at": datetime(2026, 10, 23, 10, 30),
        }
        self.items = [
            {"product_name": "Sparkler Box", "unit_price": Decimal("100.00"), "quantity": 2, "line_total": Decimal("200.00")},
            {"product_name": "Flower Pot Deluxe", "unit_price": Decimal("150.00"), "quantity": 1, "line_total": Decimal("150.00")},
        ]
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value
        self.cursor.fetchone.return_value = self.order
        self.cursor.fetchall.return_value = self.items
        patcher = patch.object(shop, "get_db", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_admin_bill_renders_only_requested_order_items_without_admin_shell(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

        response = self.client.get("/admin/orders/42/bill")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        for expected in ("#42", "A Customer", "12 Festival Street", "Sparkler Box", "Flower Pot Deluxe", "200.00", "150.00", "350.00", "Cash on delivery", "Paid"):
            self.assertIn(expected, html)
        self.assertNotIn("Admin navigation", html)
        self.assertNotIn("Customer Orders", html)
        self.cursor.execute.assert_any_call("SELECT * FROM order_items WHERE order_id = %s", (42,))

    def test_admin_bill_still_requires_login(self):
        response = self.client.get("/admin/orders/42/bill")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.location)

    def test_missing_admin_bill_order_redirects_to_orders(self):
        self.cursor.fetchone.return_value = None
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        response = self.client.get("/admin/orders/404/bill")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/admin/orders")


if __name__ == "__main__":
    unittest.main()
