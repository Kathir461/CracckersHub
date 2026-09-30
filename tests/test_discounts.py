import importlib
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import database

# Keep these tests isolated from the configured production/development database.
with patch.object(database, "init_db"):
    shop = importlib.import_module("app")


class DiscountTests(unittest.TestCase):
    def setUp(self):
        shop.app.config.update(TESTING=True, SECRET_KEY="discount-test")
        self.client = shop.app.test_client()
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value
        self.db_patch = patch.object(shop, "get_db", return_value=self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.product = dict(
            id=1, name="Sparkler", price=Decimal("250.00"),
            discount_percentage=Decimal("20.25"), selling_price=Decimal("199.38"),
            category_id=1, category_name="Sparklers", category_icon="*",
            is_active=True, stock_quantity=10, low_stock_limit=2,
        )

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True

    def cart(self, price="199.38"):
        with self.client.session_transaction() as session:
            session["cart"] = [dict(product_id=1, name="Sparkler", price=price,
                                    quantity=2, line_total=str(Decimal(price) * 2))]

    def test_price_boundaries(self):
        for discount, expected in [(0, "250.00"), ("20.25", "199.38"), (100, "0.00"), (120, "0.00")]:
            with self.subTest(discount=discount):
                self.assertEqual(shop.selling_price(dict(price=250, discount_percentage=discount)), Decimal(expected))

    def test_admin_requires_login(self):
        for method in (self.client.get, self.client.post):
            response = method("/admin/discounts")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login", response.location)
        self.db.cursor.assert_not_called()

    def test_percentage_tracks_original_price_and_rounds_half_up(self):
        self.assertEqual(shop.selling_price(dict(price="250", discount_percentage=20)), Decimal("200.00"))
        self.assertEqual(shop.selling_price(dict(price="500", discount_percentage=20)), Decimal("400.00"))
        self.assertEqual(shop.selling_price(dict(price="19.99", discount_percentage=50)), Decimal("10.00"))

    def test_percentage_can_exceed_numeric_rupee_price(self):
        self.login()
        self.cursor.fetchone.return_value = {"price": Decimal("10.00")}
        self.client.post("/admin/discounts", data=dict(product_id=1, discount_percentage="50"))
        self.db.commit.assert_called_once()

    def test_save_and_remove_discount(self):
        self.login()
        self.cursor.fetchone.return_value = self.product
        for amount in ("20.25", "0", "100"):
            response = self.client.post("/admin/discounts", data=dict(product_id=1, discount_percentage=amount))
            self.assertEqual(response.status_code, 302)
            self.cursor.execute.assert_called_with(
                "UPDATE products SET discount_percentage = %s WHERE id = %s", (Decimal(amount), 1))
        self.assertEqual(self.db.commit.call_count, 3)

    def test_invalid_discounts_do_not_save(self):
        self.login()
        self.cursor.fetchone.return_value = self.product
        for amount in ("", "bad", "NaN", "Infinity", "-1", "1.001", "101", "1e9999"):
            with self.subTest(amount=amount):
                response = self.client.post("/admin/discounts", data=dict(product_id=1, discount_percentage=amount))
                self.assertEqual(response.status_code, 302)
        self.db.commit.assert_not_called()

    def test_missing_product_does_not_save(self):
        self.login()
        self.cursor.fetchone.return_value = None
        self.client.post("/admin/discounts", data=dict(product_id=999, discount_percentage="10"))
        self.db.commit.assert_not_called()

    def test_customer_display_and_cart_on_both_pages(self):
        self.cursor.fetchone.return_value = {"id": 1}
        with patch.object(shop, "fetch_products", return_value=[self.product]), patch.object(shop, "fetch_categories", return_value=[]):
            for path in ("/products", "/gift-box"):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('<del class="original-price"', html)
                self.assertIn('data-price="199.38"', html)
                response = self.client.post(path, data={"quantity_1": "2", "price": "1"})
                self.assertEqual(response.location, "/checkout")
                with self.client.session_transaction() as session:
                    self.assertEqual(session["cart"][0]["price"], "199.38")
                    self.assertEqual(session["cart"][0]["line_total"], "398.76")

    def test_no_strikethrough_without_discount(self):
        self.product.update(discount_percentage=Decimal(0), selling_price=Decimal("250.00"))
        with patch.object(shop, "fetch_products", return_value=[self.product]), patch.object(shop, "fetch_categories", return_value=[]):
            html = self.client.get("/products").get_data(as_text=True)
        self.assertNotIn('<del class="original-price"', html)

    def test_admin_page(self):
        self.login()
        with patch.object(shop, "fetch_products", return_value=[self.product]):
            html = self.client.get("/admin/discounts").get_data(as_text=True)
        self.assertIn("Save Discount", html)
        self.assertIn('name="discount_percentage"', html)
        self.assertIn('max="100"', html)
        self.assertIn("199.38", html)

    def test_changed_cart_price_requires_review_before_order(self):
        self.cart(price="100.00")
        with patch.object(shop, "fetch_products", return_value=[self.product]):
            response = self.client.post("/checkout", data={})
            self.assertEqual(response.location, "/checkout")
            html = self.client.get("/checkout").get_data(as_text=True)
            self.assertIn("398.76", html)
        self.db.commit.assert_not_called()

    def test_order_records_discounted_price_and_total(self):
        self.cart()
        self.cursor.fetchone.return_value = self.product
        self.cursor.lastrowid = 42
        with patch.object(shop, "fetch_products", return_value=[self.product]):
            response = self.client.post("/checkout", data=dict(
                customer_name="Test", phone="1234567890", email="", address="Test street", payment_method="gpay"))
        self.assertEqual(response.location, "/bill/42")
        calls = self.cursor.execute.call_args_list
        order = next(call.args[1] for call in calls if "INSERT INTO orders" in call.args[0])
        item = next(call.args[1] for call in calls if "INSERT INTO order_items" in call.args[0])
        self.assertEqual(order[4], Decimal("398.76"))
        self.assertEqual(item[3], "199.38")
        self.assertEqual(item[6], "398.76")
        self.db.commit.assert_called_once()


class DiscountMigrationTests(unittest.TestCase):
    def test_legacy_conversion_only_when_percentage_column_is_added(self):
        for already_migrated in (False, True):
            with self.subTest(already_migrated=already_migrated):
                connection = MagicMock()
                cursor = connection.cursor.return_value
                cursor.fetchone.return_value = (1,)

                def execute(sql, *args):
                    if already_migrated and sql.startswith("ALTER TABLE products ADD COLUMN discount_percentage"):
                        raise database.mysql.connector.Error(errno=1060)

                cursor.execute.side_effect = execute
                with patch.object(database.mysql.connector, "connect", return_value=connection):
                    database.init_db()
                conversions = [call for call in cursor.execute.call_args_list
                               if "SET discount_percentage = CASE" in call.args[0]]
                self.assertEqual(len(conversions), 0 if already_migrated else 1)


if __name__ == "__main__":
    unittest.main()
