import os

import mysql.connector
from dotenv import load_dotenv
from flask import g

load_dotenv()


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "bj57i6fvsto7lojnp4ee-mysql.services.clever-cloud.com"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "ubnflkfheevwwvez"),
            password=os.getenv("MYSQL_PASSWORD", "VvOoMZAWy8xiUVP862Yp"),
            database=os.getenv("MYSQL_DATABASE", "bj57i6fvsto7lojnp4ee"),
        )
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "bj57i6fvsto7lojnp4ee-mysql.services.clever-cloud.com"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "ubnflkfheevwwvez"),
        password=os.getenv("MYSQL_PASSWORD", "VvOoMZAWy8xiUVP862Yp"),
    )
    cursor = connection.cursor()
    database = os.getenv("MYSQL_DATABASE", "bj57i6fvsto7lojnp4ee")
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
    cursor.execute(f"USE `{database}`")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            offer_percentage DECIMAL(5, 2) NOT NULL DEFAULT 0,
            description TEXT,
            image_url VARCHAR(255),
            product_category ENUM('shop', 'gift_box') NOT NULL DEFAULT 'shop',
            stock_quantity INT NOT NULL DEFAULT 0,
            low_stock_limit INT NOT NULL DEFAULT 10,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    for alter_sql in [
        "ALTER TABLE products ADD COLUMN image_url VARCHAR(255)",
        "ALTER TABLE products ADD COLUMN product_category ENUM('shop', 'gift_box') NOT NULL DEFAULT 'shop'",
        "ALTER TABLE products ADD COLUMN stock_quantity INT NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN low_stock_limit INT NOT NULL DEFAULT 10",
    ]:
        try:
            cursor.execute(alter_sql)
        except mysql.connector.Error:
            pass

    cursor.execute("UPDATE products SET stock_quantity = COALESCE(stock_quantity, 0)")
    cursor.execute("UPDATE products SET low_stock_limit = COALESCE(low_stock_limit, 10)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(150) NOT NULL,
            phone VARCHAR(30) NOT NULL,
            email VARCHAR(150) NOT NULL,
            address TEXT NOT NULL,
            total_amount DECIMAL(10, 2) NOT NULL,
            payment_method ENUM('gpay', 'card') NOT NULL,
            payment_status VARCHAR(50) NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT,
            product_name VARCHAR(150) NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            offer_percentage DECIMAL(5, 2) NOT NULL,
            quantity INT NOT NULL,
            line_total DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO products (name, price, offer_percentage, description, product_category, stock_quantity, low_stock_limit)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                ("Sparkler Box", 120.00, 10.00, "Classic hand sparklers", "shop", 45, 10),
                ("Flower Pot Deluxe", 250.00, 15.00, "Bright fountain crackers", "shop", 20, 8),
                ("Ground Chakra", 180.00, 5.00, "Color spinning ground wheel", "shop", 30, 10),
                ("Rocket Pack", 320.00, 12.00, "Assorted sky rockets", "shop", 15, 5),
                ("Gift Spinner Pack", 750.00, 80.00, "Gift-ready novelty spinner pack", "gift_box", 25, 6),
            ],
        )

    connection.commit()
    cursor.close()
    connection.close()
