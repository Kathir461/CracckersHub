import importlib
import unittest
from unittest.mock import MagicMock, patch

import database

with patch.object(database, "init_db"):
    shop = importlib.import_module("app")


class AdminListTests(unittest.TestCase):
    def setUp(self):
        shop.app.config.update(TESTING=True, SECRET_KEY="list-tests")
        self.client = shop.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value
        self.cursor.fetchall.return_value = []
        patcher = patch.object(shop, "get_db", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_order_filters_are_parameterized(self):
        response = self.client.get("/admin/orders?search=O%27Brien&status=Paid")
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("payment_status = %s", sql)
        self.assertNotIn("O'Brien", sql)
        self.assertEqual(params, ("%O'Brien%",) * 4 + ("Paid",))
        self.assertIn("No orders match", response.get_data(as_text=True))

    def test_invalid_status_falls_back_to_all(self):
        self.client.get("/admin/orders?status=invalid")
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn("WHERE", sql)
        self.assertEqual(params, ())

    def test_category_editor_and_missing_category(self):
        category = dict(id=1, category_name="Sparklers", icon="*", display_order=2, is_active=True, description="")
        with patch.object(shop, "fetch_categories", return_value=[category]):
            response = self.client.get("/admin/categories/1/edit")
            self.assertEqual(response.status_code, 200)
            self.assertIn('name="display_order"', response.get_data(as_text=True))
            self.assertEqual(self.client.get("/admin/categories/999/edit").location, "/admin/categories")

    def test_category_edit_requires_admin(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get("/admin/categories/1/edit").location, "/admin/login")


if __name__ == "__main__":
    unittest.main()
