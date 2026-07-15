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
        database=os.getenv("MYSQL_DATABASE", "bj57i6fvsto7lojnp4ee"),
    )
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INT AUTO_INCREMENT PRIMARY KEY,
            category_name VARCHAR(150) NOT NULL UNIQUE,
            icon VARCHAR(20) NOT NULL DEFAULT 'F',
            description TEXT,
            display_order INT NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    default_categories = [
        ("Sparklers", "✨", "Classic sparklers for all celebrations.", 1, True),
        ("Flower Pots", "🌋", "Bright fountain-style crackers.", 2, True),
        ("Ground Chakkars", "🌀", "Spinning ground fireworks.", 3, True),
        ("Rockets", "🚀", "Sky-shot rocket collections.", 4, True),
        ("Bombs", "💥", "Sound crackers and festive bombs.", 5, True),
        ("Gift Boxes", "🎁", "Ready-made assorted celebration packs.", 6, True),
        ("Fancy Crackers", "🎆", "Premium novelty crackers.", 7, True),
        ("Electric Crackers", "⚡", "Electric and modern cracker collections.", 8, True),
        ("Colour Crackers", "🌈", "Colourful crackers for families.", 9, True),
        ("Kids Special", "🧒", "Kid-friendly celebration items.", 10, True),
        ("Festival Offers", "🏷️", "Seasonal featured products.", 11, True),
        ("Combo Packs", "📦", "Value combo cracker bundles.", 12, True),
    ]
    cursor.executemany(
        """
        INSERT IGNORE INTO categories
            (category_name, icon, description, display_order, is_active)
        VALUES (%s, %s, %s, %s, %s)
        """,
        default_categories,
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            description TEXT,
            image_url VARCHAR(255),
            category_id INT,
            stock_quantity INT NOT NULL DEFAULT 0,
            low_stock_limit INT NOT NULL DEFAULT 10,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        )
        """
    )

    for alter_sql in [
        "ALTER TABLE products ADD COLUMN image_url VARCHAR(255)",
        "ALTER TABLE products ADD COLUMN category_id INT",
        "ALTER TABLE products ADD COLUMN stock_quantity INT NOT NULL DEFAULT 0",
        "ALTER TABLE products ADD COLUMN low_stock_limit INT NOT NULL DEFAULT 10",
        "ALTER TABLE products ADD CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL",
    ]:
        try:
            cursor.execute(alter_sql)
        except mysql.connector.Error:
            pass

    cursor.execute("UPDATE products SET stock_quantity = COALESCE(stock_quantity, 0)")
    cursor.execute("UPDATE products SET low_stock_limit = COALESCE(low_stock_limit, 10)")
    try:
        cursor.execute(
            """
            UPDATE products p
            JOIN categories c ON c.category_name = 'Gift Boxes'
            SET p.category_id = c.id
            WHERE p.category_id IS NULL AND p.product_category = 'gift_box'
            """
        )
        cursor.execute(
            """
            UPDATE products p
            JOIN categories c ON c.category_name = 'Sparklers'
            SET p.category_id = c.id
            WHERE p.category_id IS NULL
            """
        )
    except mysql.connector.Error:
        cursor.execute(
            """
            UPDATE products p
            JOIN categories c ON c.category_name = 'Sparklers'
            SET p.category_id = c.id
            WHERE p.category_id IS NULL
            """
        )

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
            INSERT INTO products (name, price, description, category_id, stock_quantity, low_stock_limit)
            SELECT %s, %s, %s, c.id, %s, %s
            FROM categories c
            WHERE c.category_name = %s
            """,
            [
                ("Sparkler Box", 120.00, "Classic hand sparklers", 45, 10, "Sparklers"),
                ("Flower Pot Deluxe", 250.00, "Bright fountain crackers", 20, 8, "Flower Pots"),
                ("Ground Chakra", 180.00, "Color spinning ground wheel", 30, 10, "Ground Chakkars"),
                ("Rocket Pack", 320.00, "Assorted sky rockets", 15, 5, "Rockets"),
                ("Gift Spinner Pack", 750.00, "Gift-ready novelty spinner pack", 25, 6, "Gift Boxes"),
            ],
        )

    connection.commit()
    cursor.close()
    connection.close()
