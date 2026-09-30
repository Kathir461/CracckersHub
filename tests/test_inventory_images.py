import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.datastructures import FileStorage
import database

with patch.object(database, "init_db"):
    shop = importlib.import_module("app")


class InventoryImageTests(unittest.TestCase):
    def setUp(self):
        shop.app.config.update(TESTING=True, SECRET_KEY="inventory-test")
        self.client = shop.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value
        patcher = patch.object(shop, "get_db", return_value=self.db)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.product = dict(id=1, name="Sparkler", price=100, discount_percentage=20,
                            selling_price=80, image_url="/static/uploads/missing.jpg",
                            category_id=1, category_name="Sparklers", stock_quantity=25,
                            low_stock_limit=0, is_active=True)

    def test_catalog_and_editor_have_no_stock_controls(self):
        with patch.object(shop, "fetch_products", return_value=[self.product]), patch.object(shop, "fetch_categories", return_value=[]):
            for route in ("/admin/products", "/admin/products/1/edit"):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertNotIn('name="stock_quantity"', html)
                self.assertNotIn('name="low_stock_limit"', html)
                self.assertIn("product-placeholder.svg", html)
            html = self.client.get("/admin/inventory").get_data(as_text=True)
            self.assertIn('name="stock_quantity"', html)
            self.assertIn('name="low_stock_limit"', html)
            self.assertIn('value="0"', html)
            self.assertIn("IN STOCK", html)

    def test_edit_product_does_not_write_stock_or_discount(self):
        self.cursor.fetchone.return_value = ("/static/uploads/original.jpg",)
        response = self.client.post("/admin/products/1/edit", data=dict(
            name="Renamed", price="200", category_id="1", is_active="on",
            stock_quantity="0", low_stock_limit="10"))
        self.assertEqual(response.status_code, 302)
        sql, params = self.cursor.execute.call_args.args
        self.assertNotIn("stock_quantity", sql)
        self.assertNotIn("low_stock_limit", sql)
        self.assertNotIn("discount_percentage", sql)
        self.assertIn("/static/uploads/original.jpg", params)
        self.assertEqual(sql.count("%s"), len(params))

    def test_inventory_updates_only_stock(self):
        self.cursor.fetchone.return_value = (1,)
        response = self.client.post("/admin/inventory/1/edit", data=dict(stock_quantity="40", low_stock_limit="0"))
        self.assertEqual(response.location, "/admin/inventory")
        self.cursor.execute.assert_called_with(
            "UPDATE products SET stock_quantity = %s, low_stock_limit = %s WHERE id = %s", (40, 0, 1))
        self.db.commit.assert_called_once()

    def test_invalid_stock_is_rejected(self):
        for stock, limit in [("-1", "5"), ("1.5", "5"), ("3", "-1"), ("", "5"), ("2147483648", "0")]:
            self.client.post("/admin/inventory/1/edit", data=dict(stock_quantity=stock, low_stock_limit=limit))
        self.db.commit.assert_not_called()

    def test_inventory_requires_admin(self):
        with self.client.session_transaction() as session:
            session.clear()
        for path, method in [("/admin/inventory", self.client.get), ("/admin/inventory/1/edit", self.client.post)]:
            self.assertEqual(method(path).location, "/admin/login")

    def test_quick_adjustment_and_zero_floor(self):
        self.cursor.fetchone.return_value = {"stock_quantity": 0}
        response = self.client.post("/admin/products/1/adjust-stock", data={"delta": "-1"})
        self.assertEqual(response.location, "/admin/inventory")
        self.cursor.execute.assert_called_with("UPDATE products SET stock_quantity = %s WHERE id = %s", (0, 1))

    def test_image_paths_and_placeholder(self):
        with shop.app.test_request_context():
            for path in (None, "/static/uploads/missing.jpg", "javascript:alert(1)", "/static/../.env"):
                self.assertEqual(shop.product_image_src(path), "/static/images/product-placeholder.svg")
            self.assertEqual(shop.product_image_src("https://example.com/photo.jpg"), "https://example.com/photo.jpg")
            self.assertEqual(shop.product_image_src("static/images/product-placeholder.svg"), "/static/images/product-placeholder.svg")

    def test_local_upload_saves_file_and_unique_urls(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), patch.object(shop, "UPLOAD_FOLDER", folder), shop.app.test_request_context():
            urls = []
            for _ in range(2):
                upload = FileStorage(stream=io.BytesIO(b"image data"), filename="photo.jpg")
                urls.append(shop.save_product_image(upload))
            self.assertNotEqual(*urls)
            self.assertEqual(len(list(Path(folder).iterdir())), 2)

    def test_cloudinary_uses_sdk_config_and_does_not_fall_back_on_failure(self):
        import cloudinary.uploader  # Initialize the SDK before mocking its config.
        env = dict(CLOUDINARY_CLOUD_NAME="test", CLOUDINARY_API_KEY="test", CLOUDINARY_API_SECRET="test")
        with patch.dict(os.environ, env, clear=True), patch("cloudinary.config") as config, patch("cloudinary.uploader.upload") as upload, shop.app.test_request_context():
            upload.return_value = {"secure_url": "https://example.com/photo.jpg"}
            image_file = FileStorage(stream=io.BytesIO(b"image data"), filename="photo.jpg")
            self.assertEqual(shop.save_product_image(image_file), "https://example.com/photo.jpg")
            config.assert_called_once_with(cloud_name="test", api_key="test", api_secret="test", secure=True)
            upload.side_effect = RuntimeError("Unavailable")
            image_file.seek(0)
            self.assertIsNone(shop.save_product_image(image_file))

    def test_failed_upload_does_not_save_product(self):
        self.cursor.fetchone.return_value = ("/static/uploads/original.jpg",)
        with patch.object(shop, "save_product_image", return_value=None):
            self.client.post("/admin/products/1/edit", data={
                "name": "Test", "price": "100", "image": (io.BytesIO(b"bad"), "photo.jpg")})
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
