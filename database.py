import os

import mysql.connector
from dotenv import load_dotenv
from flask import g

load_dotenv()


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "kathir"),
            database=os.getenv("MYSQL_DATABASE", "crackershub"),
        )
    return g.db


def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", "kathir"),
    )
    cursor = connection.cursor()
    database = os.getenv("MYSQL_DATABASE", "crackershub")
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
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Add image_url column if it doesn't exist (for existing databases)
    try:
        cursor.execute(
            """
            ALTER TABLE products
            ADD COLUMN image_url VARCHAR(255)
            """
        )
    except mysql.connector.Error:
        # Column already exists, ignore the error
        pass

    # Add product_category column if it doesn't exist (for existing databases)
    try:
        cursor.execute(
            """
            ALTER TABLE products
            ADD COLUMN product_category ENUM('shop', 'gift_box') NOT NULL DEFAULT 'shop'
            """
        )
    except mysql.connector.Error:
        # Column already exists, ignore the error
        pass

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
            INSERT INTO products (name, price, offer_percentage, description, product_category)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                ("Sparkler Box", 120.00, 10.00, "Classic hand sparklers", "shop"),
                ("Flower Pot Deluxe", 250.00, 15.00, "Bright fountain crackers", "shop"),
                ("Ground Chakra", 180.00, 5.00, "Color spinning ground wheel", "shop"),
                ("Rocket Pack", 320.00, 12.00, "Assorted sky rockets", "shop"),
                ("Gift Spinner Pack", 750.00, 80.00, "Gift-ready novelty spinner pack", "gift_box"),
            ],
        )

    connection.commit()
    cursor.close()
    connection.close()
