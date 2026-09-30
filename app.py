import os
import mysql.connector
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4
    
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from database import close_db, get_db, init_db

# Simple per-request performance logging (admin only)
import time as _perf_time


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.teardown_appcontext(close_db)

# Image upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_product_image(image_file):
    """Upload product image to Cloudinary when configured, otherwise save locally."""
    if not image_file:
        return None

    filename = getattr(image_file, "filename", None)
    if not filename or str(filename).strip() == "":
        return None

    if not allowed_file(image_file.filename):
        flash("Only image files (PNG, JPG, JPEG, GIF, WebP) are allowed.", "error")
        return None

    image_file.seek(0, os.SEEK_END)
    size = image_file.tell()
    image_file.seek(0)
    if size == 0 or size > MAX_FILE_SIZE:
        flash("Choose a non-empty image smaller than 5MB.", "error")
        return None

    # Configure the SDK itself, not attributes on its config function.
    cloudinary_ready = bool(os.getenv("CLOUDINARY_URL") or all(
        os.getenv(key) for key in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    ))
    if cloudinary_ready:
        try:
            import cloudinary
            from cloudinary.uploader import upload

            if not os.getenv("CLOUDINARY_URL"):
                cloudinary.config(
                    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
                    api_key=os.getenv("CLOUDINARY_API_KEY"),
                    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
                    secure=True,
                )
            options = {"resource_type": "image", "folder": "products"}
            if os.getenv("CLOUDINARY_UPLOAD_PRESET"):
                options["upload_preset"] = os.getenv("CLOUDINARY_UPLOAD_PRESET")
            result = upload(image_file, **options)
            if not result.get("secure_url"):
                raise ValueError("Image upload returned no URL")
            return result["secure_url"]
        except Exception:
            app.logger.warning("Product image upload to Cloudinary failed.")
            flash("Image upload failed. Please try again; the product has not been saved.", "error")
            return None

    # Local development uploads need persistent storage on a hosted deployment.
    try:
        original_name = secure_filename(filename)
        if not original_name:
            flash("Please choose an image with a valid filename.", "error")
            return None
        safe_name = f"{uuid4().hex}_{original_name}"
        image_file.save(os.path.join(UPLOAD_FOLDER, safe_name))
        return url_for("static", filename=f"uploads/{safe_name}")
    except OSError:
        flash("Unable to save the image. Please try again.", "error")
        return None


@app.template_filter("product_image_src")
def product_image_src(value):
    fallback = url_for("static", filename="images/product-placeholder.svg")
    value = str(value or "").strip().replace("\\", "/")
    if value.startswith(("https://", "http://")):
        return value
    if value.startswith("uploads/"):
        value = "static/" + value
    if value.startswith("static/"):
        value = "/" + value
    if value.startswith("/static/"):
        relative = unquote(urlsplit(value).path[len("/static/"):])
        root = Path(app.static_folder).resolve()
        candidate = (root / relative).resolve()
        if root in candidate.parents and candidate.is_file():
            return url_for("static", filename=relative)
    return fallback



def shop_details():
    return {
        "name": os.getenv("SHOP_NAME", "Cracckers Hub"),
        "phone": os.getenv("SHOP_PHONE", "8248627753"),
        "email": os.getenv("SHOP_EMAIL", "cracckershubsivakasi@gmail.com"),
        "address": os.getenv(
            "SHOP_ADDRESS",
            "No - 3 , balan nagar , Aduthurai , Thanjavur district. 612101",
        ),
        "icon_url": os.getenv(
            "APP_ICON_URL",
            "https://res.cloudinary.com/dkrx3kqey/image/upload/v1780567963/logo1_xm3vjy.jpg",
        ),
    }



@app.context_processor
def inject_globals():
    return {
        "shop": shop_details(),
        "get_stock_status": get_stock_status,
    }


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin page.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def selling_price(product):
    price = money(product["price"])
    percentage = Decimal(str(product.get("discount_percentage", 0) or 0))
    percentage = min(Decimal("100"), max(Decimal("0"), percentage))
    return (price * (100 - percentage) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_stock_status(product):
    stock = int(product.get("stock_quantity", 0) or 0)
    limit = int(product.get("low_stock_limit") if product.get("low_stock_limit") is not None else 10)
    if stock <= 0:
        return {"label": "OUT OF STOCK", "class": "stock-badge danger"}
    if stock <= limit:
        return {"label": "LOW STOCK", "class": "stock-badge warning"}
    return {"label": "IN STOCK", "class": "stock-badge success"}


def fetch_categories(active_only=False):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT
            c.*,
            COUNT(p.id) AS products_count,
            COALESCE(SUM(CASE WHEN COALESCE(p.stock_quantity, 0) > 0 THEN 1 ELSE 0 END), 0) AS products_in_stock,
            COALESCE(SUM(CASE WHEN COALESCE(p.stock_quantity, 0) <= 0 THEN 1 ELSE 0 END), 0) AS products_out_of_stock
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
    """
    params = []
    if active_only:
        query += " WHERE c.is_active = 1"
    query += " GROUP BY c.id ORDER BY c.display_order, c.category_name"
    cursor.execute(query, tuple(params))
    return cursor.fetchall()


def fetch_products(active_only=True, category_id=None):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT
            p.*,
            c.category_name,
            c.icon AS category_icon,
            c.display_order AS category_order,
            c.is_active AS category_is_active
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
    """
    conditions = []
    params = []

    if active_only:
        conditions.append("p.is_active = 1")
        conditions.append("(c.is_active = 1 OR p.category_id IS NULL)")
    if category_id:
        conditions.append("p.category_id = %s")
        params.append(category_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY COALESCE(c.display_order, 9999), COALESCE(c.category_name, 'Uncategorized'), p.name"
    cursor.execute(query, tuple(params))
    products = cursor.fetchall()
    for product in products:
        product["selling_price"] = selling_price(product)
    return products


def group_products_by_category(products):
    groups = []
    category_map = {}
    for product in products:
        category_id = product.get("category_id") or 0
        if category_id not in category_map:
            group = {
                "id": category_id,
                "name": product.get("category_name") or "Uncategorized",
                "icon": product.get("category_icon") or "🔥",
                "products": [],
            }
            category_map[category_id] = group
            groups.append(group)
        category_map[category_id]["products"].append(product)
    return groups


def get_category_summary():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM categories")
    total_categories = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM categories WHERE is_active = 1")
    active_categories = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM products")
    total_products = cursor.fetchone()["total"]
    cursor.execute(
        """
        SELECT c.category_name, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id
        ORDER BY product_count DESC, c.category_name
        LIMIT 1
        """
    )
    largest = cursor.fetchone()
    return {
        "total_categories": total_categories,
        "active_categories": active_categories,
        "total_products": total_products,
        "largest_category": largest["category_name"] if largest else "None",
    }


@app.route("/")
def home():
    return render_template("customer/home.html")






@app.route("/about")
def about():
    return render_template("customer/about.html")


@app.route("/gift-box", methods=["GET", "POST"])
def gift_box():

    # Gift box page uses the same interactive table + checkout flow as the shop.
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id FROM categories WHERE category_name = %s AND is_active = 1", ("Gift Boxes",))
    gift_category = cursor.fetchone()
    products = fetch_products(active_only=True, category_id=gift_category["id"] if gift_category else None)

    if request.method == "POST":
        selected_items = []
        for product in products:
            quantity_raw = request.form.get(f"quantity_{product['id']}", "0")
            try:
                quantity = int(quantity_raw)
            except ValueError:
                quantity = 0

            if quantity > 0:
                price = selling_price(product)
                selected_items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "price": str(price),
                        "quantity": quantity,
                        "line_total": str(money(price * quantity)),
                    }
                )

        if not selected_items:
            flash("Enter quantity for at least one product.", "error")
            return redirect(url_for("gift_box"))

        session["cart"] = selected_items
        return redirect(url_for("checkout"))

    return render_template("customer/gift_box.html", products=products, product_groups=group_products_by_category(products))


@app.route("/products", methods=["GET", "POST"])
def customer_products():
    selected_category_id = request.args.get("category_id", type=int)
    products = fetch_products(active_only=True, category_id=selected_category_id)
    categories = fetch_categories(active_only=True)
    if request.method == "POST":
        selected_items = []
        for product in products:
            quantity_raw = request.form.get(f"quantity_{product['id']}", "0")
            try:
                quantity = int(quantity_raw)
            except ValueError:
                quantity = 0

            if quantity > 0:
                price = selling_price(product)
                selected_items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "price": str(price),
                        "quantity": quantity,
                        "line_total": str(money(price * quantity)),
                    }
                )

        if not selected_items:
            flash("Enter quantity for at least one product.", "error")
            return redirect(url_for("customer_products"))

        session["cart"] = selected_items
        return redirect(url_for("checkout"))

    return render_template(
        "customer/products.html",
        products=products,
        product_groups=group_products_by_category(products),
        categories=categories,
        selected_category_id=selected_category_id,
    )


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer_products"))

    # Refresh saved carts so discounts changed by the admin also apply at checkout.
    current_products = {product["id"]: product for product in fetch_products()}
    prices_changed = False
    for item in cart:
        product = current_products.get(item["product_id"])
        if not product:
            flash(f"{item['name']} is no longer available. Please update your cart.", "error")
            return redirect(url_for("customer_products"))
        price = selling_price(product)
        prices_changed = prices_changed or money(item["price"]) != price
        item["price"] = str(price)
        item["line_total"] = str(money(price * item["quantity"]))
    session["cart"] = cart
    if prices_changed:
        flash("Product prices have changed. Please review your updated total before placing your order.", "success")
        if request.method == "POST":
            return redirect(url_for("checkout"))

    total = sum(Decimal(item["line_total"]) for item in cart)

    if request.method == "POST":
        customer_name = request.form["customer_name"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()  # Optional
        address = request.form["address"].strip()
        payment_method = request.form["payment_method"]

        if not customer_name or not phone or not address:
            flash("Please fill name, phone, and delivery address.", "error")
            return render_template("customer/checkout.html", cart=cart, total=total)

        db = get_db()
        cursor = db.cursor(dictionary=True)

        for item in cart:
            cursor.execute(
                "SELECT id, stock_quantity, name FROM products WHERE id = %s AND is_active = 1",
                (item["product_id"],),
            )
            product = cursor.fetchone()
            if not product:
                flash(f"{item['name']} is no longer available.", "error")
                return render_template("customer/checkout.html", cart=cart, total=total)

            available = int(product.get("stock_quantity", 0) or 0)
            requested = int(item.get("quantity", 0))
            if requested > available:
                flash(f"Only {available} items available for {item['name']}.", "error")
                return render_template("customer/checkout.html", cart=cart, total=total)
            if available <= 0:
                flash(f"{item['name']} is out of stock.", "error")
                return render_template("customer/checkout.html", cart=cart, total=total)

        cursor.execute(
            """
            INSERT INTO orders
                (customer_name, phone, email, address, total_amount, payment_method, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (customer_name, phone, email, address, total, payment_method, "Paid"),
        )
        order_id = cursor.lastrowid

        for item in cart:
            cursor.execute(
                """
                INSERT INTO order_items
                    (order_id, product_id, product_name, unit_price, offer_percentage, quantity, line_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    item["product_id"],
                    item["name"],
                    item["price"],
                    0,
                    item["quantity"],
                    item["line_total"],
                ),
            )

            cursor.execute(
                "UPDATE products SET stock_quantity = GREATEST(stock_quantity - %s, 0) WHERE id = %s",
                (item["quantity"], item["product_id"]),
            )

        db.commit()
        session.pop("cart", None)
        flash(
            "Order placed successfully. Your bill is ready.",
            "success",
        )
        return redirect(url_for("customer_bill", order_id=order_id))

    return render_template("customer/checkout.html", cart=cart, total=total)


@app.route("/bill/<int:order_id>")
def customer_bill(order_id):
    order, items = get_order_with_items(order_id)
    if not order:
        flash("Bill not found.", "error")
        return redirect(url_for("customer_products"))

    return render_template(
        "customer/bill.html",
        order=order,
        items=items,
    )


@app.route("/history", methods=["GET", "POST"])
def order_history():
    orders = []
    lookup = ""
    if request.method == "POST":
        lookup = request.form["lookup"].strip()
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT * FROM orders
            WHERE phone = %s OR email = %s
            ORDER BY created_at DESC
            """,
            (lookup, lookup),
        )
        orders = cursor.fetchall()
        if not orders:
            flash("No orders found for that phone number or email.", "error")

    return render_template("customer/history.html", orders=orders, lookup=lookup)


@app.route("/contact")
def contact():
    return render_template("customer/contact.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == os.getenv("ADMIN_USERNAME", "admin") and password == os.getenv(
            "ADMIN_PASSWORD", "admin123"
        ):
            session["admin_logged_in"] = True
            flash("Welcome back, admin.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.", "error")

    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    import time as _t
    _t0 = _t.perf_counter()
    db = get_db()

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS count FROM products WHERE is_active = 1")
    product_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) AS count FROM orders")
    order_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) AS total FROM orders")
    sales_total = cursor.fetchone()["total"]

    # Daily analytics (auto resets because we filter by today's date)
    cursor.execute(
        """
        SELECT COALESCE(SUM(oi.line_total), 0) AS revenue
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.created_at >= CURDATE()
          AND o.created_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
        """
    )
    daily_revenue = cursor.fetchone()["revenue"]

    cursor.execute(
        """
        SELECT oi.product_name, SUM(oi.quantity) AS units_sold
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.id
        WHERE o.created_at >= CURDATE()
          AND o.created_at < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
        GROUP BY oi.product_name
        ORDER BY units_sold DESC, oi.product_name ASC
        LIMIT 1
        """
    )
    daily_best_row = cursor.fetchone()
    daily_best_selling_product = daily_best_row["product_name"] if daily_best_row else "None"
    cursor.execute("SELECT COUNT(*) AS count FROM products WHERE stock_quantity <= 0")
    out_of_stock_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) AS count FROM products WHERE stock_quantity > 0 AND stock_quantity <= COALESCE(low_stock_limit, 10)")
    low_stock_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COALESCE(SUM(stock_quantity), 0) AS total FROM products")
    inventory_quantity = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS count FROM categories")
    total_categories = cursor.fetchone()["count"]
    cursor.execute(
        """
        SELECT c.category_name, COUNT(p.id) AS product_count
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
        GROUP BY c.id
        ORDER BY product_count DESC, c.category_name
        LIMIT 1
        """
    )
    largest_category_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT COALESCE(c.category_name, 'Uncategorized') AS category_name,
               COALESCE(SUM(oi.line_total), 0) AS revenue
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY category_name
        ORDER BY revenue DESC
        LIMIT 1
        """
    )
    highest_revenue_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT COALESCE(c.category_name, 'Uncategorized') AS category_name,
               COALESCE(SUM(oi.line_total), 0) AS revenue
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY category_name
        ORDER BY revenue ASC
        LIMIT 1
        """
    )
    lowest_revenue_row = cursor.fetchone()
    resp = render_template(
        "admin/dashboard.html",

        product_count=product_count,
        order_count=order_count,
        sales_total=sales_total,
        daily_revenue=daily_revenue,
        daily_best_selling_product=daily_best_selling_product,
        out_of_stock_count=out_of_stock_count,
        low_stock_count=low_stock_count,
        inventory_quantity=inventory_quantity,
        total_categories=total_categories,
        largest_category=largest_category_row["category_name"] if largest_category_row else "None",
        highest_revenue_category=highest_revenue_row["category_name"] if highest_revenue_row else "None",
        lowest_revenue_category=lowest_revenue_row["category_name"] if lowest_revenue_row else "None",
    )
    app.logger.info("[perf] /admin total=%.3f s", _t.perf_counter() - _t0)
    return resp



@app.route("/admin/sales-details")
@admin_required
def admin_sales_details():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Product rows grouped under each category
    cursor.execute(
        """
        SELECT
            COALESCE(c.id, 0) AS category_id,
            COALESCE(CONVERT(c.category_name USING utf8mb4), 'Uncategorized') AS category_name,
            COALESCE(CONVERT(c.icon USING utf8mb4), 'F') AS category_icon,
            oi.product_name,
            SUM(oi.quantity) AS total_quantity,
            SUM(oi.line_total) AS total_sales
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY category_id, category_name, category_icon, oi.product_name
        ORDER BY COALESCE(c.display_order, 9999), category_name, total_sales DESC
        """
    )
    sales_rows = cursor.fetchall()

    # Build category groups from the product rows
    sales_groups = []
    group_map = {}
    for row in sales_rows:
        key = row["category_id"]
        if key not in group_map:
            group_map[key] = {
                "category_name": row["category_name"],
                "category_icon": row["category_icon"],
                "rows": [],
            }
            sales_groups.append(group_map[key])
        group_map[key]["rows"].append(row)

    # Category totals (SQL GROUP BY to avoid mismatch)
    cursor.execute(
        """
        SELECT
            COALESCE(c.id, 0) AS category_id,
            COALESCE(CONVERT(c.category_name USING utf8mb4), 'Uncategorized') AS category_name,
            COALESCE(CONVERT(c.icon USING utf8mb4), 'F') AS category_icon,
            SUM(oi.quantity) AS total_units,
            SUM(oi.line_total) AS total_revenue
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY category_id, category_name, category_icon
        """
    )
    category_totals_rows = cursor.fetchall() or []
    category_totals_map = {
        int(r["category_id"]): {
            "total_units": int(r["total_units"] or 0),
            "total_revenue": float(r["total_revenue"] or 0),
        }
        for r in category_totals_rows
    }

    # Attach SQL totals to the groups
    for group in sales_groups:
        # We may not have category_id in group, so recompute by matching name/icon
        # Better approach would pass category_id too, but template only needs correct totals.
        # Find matching totals row by category_name
        match = None
        for ct in category_totals_rows:
            if ct["category_name"] == group["category_name"] and ct["category_icon"] == group["category_icon"]:
                match = category_totals_map.get(int(ct["category_id"]))
                if match:
                    break
        group["total_units"] = match["total_units"] if match else 0
        group["total_revenue"] = match["total_revenue"] if match else 0.0

    # Overall totals + KPIs
    cursor.execute("SELECT COALESCE(SUM(line_total), 0) AS grand_total FROM order_items")
    total_sales = cursor.fetchone()["grand_total"] or 0

    cursor.execute("SELECT COALESCE(SUM(quantity), 0) AS total_units FROM order_items")
    total_units = cursor.fetchone()["total_units"] or 0

    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()["total_orders"] or 0

    avg_order_value = (float(total_sales) / float(total_orders)) if total_orders else 0.0

    cursor.execute(
        """
        SELECT
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            SUM(oi.line_total) AS revenue
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY COALESCE(c.category_name, 'Uncategorized')
        ORDER BY revenue DESC
        LIMIT 1
        """
    )
    best_cat_row = cursor.fetchone() or {}
    best_selling_category = best_cat_row.get("category_name") or "Uncategorized"

    cursor.execute(
        """
        SELECT
            oi.product_name,
            SUM(oi.quantity) AS units_sold
        FROM order_items oi
        GROUP BY oi.product_name
        ORDER BY units_sold DESC
        LIMIT 1
        """
    )
    best_prod_row = cursor.fetchone() or {}
    best_selling_product = best_prod_row.get("product_name") or ""

    # Top 5 products
    cursor.execute(
        """
        SELECT
            oi.product_name,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.line_total) AS revenue
        FROM order_items oi
        GROUP BY oi.product_name
        ORDER BY revenue DESC
        LIMIT 5
        """
    )
    top_products = cursor.fetchall() or []

    # Top 5 categories
    cursor.execute(
        """
        SELECT
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            SUM(oi.quantity) AS units_sold,
            SUM(oi.line_total) AS revenue
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        LEFT JOIN categories c ON c.id = p.category_id
        GROUP BY COALESCE(c.category_name, 'Uncategorized')
        ORDER BY revenue DESC
        LIMIT 5
        """
    )
    top_categories = cursor.fetchall() or []

    return render_template(
        "admin/sales_details.html",
        sales_groups=sales_groups,
        total_sales=total_sales,
        total_units=total_units,
        total_orders=total_orders,
        avg_order_value=avg_order_value,
        best_selling_category=best_selling_category,
        best_selling_product=best_selling_product,
        top_products=top_products,
        top_categories=top_categories,
    )




@app.route("/admin/sales_details")
@admin_required
def admin_sales_details_compat():
    # Backward-compatible route for old links using underscore.
    return redirect(url_for("admin_sales_details"))


@app.route("/admin/categories")
@admin_required
def admin_categories():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")
    sort = request.args.get("sort", "display_order")

    query = """
        SELECT
            c.*,
            COUNT(p.id) AS products_count,
            COALESCE(SUM(CASE WHEN COALESCE(p.stock_quantity, 0) > 0 THEN 1 ELSE 0 END), 0) AS products_in_stock,
            COALESCE(SUM(CASE WHEN COALESCE(p.stock_quantity, 0) <= 0 THEN 1 ELSE 0 END), 0) AS products_out_of_stock
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.id
    """
    conditions = []
    params = []
    if search:
        conditions.append("(c.category_name LIKE %s OR c.description LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status == "active":
        conditions.append("c.is_active = 1")
    elif status == "inactive":
        conditions.append("c.is_active = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    sort_map = {
        "name": "c.category_name",
        "products": "products_count DESC",
        "display_order": "c.display_order",
        "status": "c.is_active DESC, c.display_order",
    }
    query += f" GROUP BY c.id ORDER BY {sort_map.get(sort, 'c.display_order')}, c.category_name"
    cursor.execute(query, tuple(params))
    categories = cursor.fetchall()

    return render_template(
        "admin/categories.html",
        title="Categories",
        categories=categories,
        summary=get_category_summary(),
        search=search,
        status=status,
        sort=sort,
    )


@app.route("/admin/categories/add", methods=["POST"])
@admin_required
def add_category():
    db = get_db()
    cursor = db.cursor()

    try:
        category_name = request.form.get("category_name", "").strip()
        icon = request.form.get("icon", "*").strip() or "*"
        description = request.form.get("description", "").strip()

        # Safely convert display order to an integer.
        try:
            display_order = int(
                request.form.get("display_order", "0") or "0"
            )
        except (TypeError, ValueError):
            display_order = 0

        is_active = 1 if request.form.get("is_active") else 0

        # Validate category name.
        if not category_name:
            flash("Category name is required.", "error")
            return redirect(url_for("admin_categories"))

        # Check for duplicate category names.
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE category_name = %s
            LIMIT 1
            """,
            (category_name,),
        )

        existing_category = cursor.fetchone()

        if existing_category:
            flash(
                "A category with this name already exists.",
                "error",
            )
            return redirect(url_for("admin_categories"))

        # Insert the category.
        cursor.execute(
            """
            INSERT INTO categories
                (category_name, icon, description, display_order, is_active)
            VALUES
                (%s, %s, %s, %s, %s)
            """,
            (
                category_name,
                icon,
                description,
                display_order,
                is_active,
            ),
        )

        db.commit()

        flash("Category added successfully.", "success")

    except mysql.connector.Error as e:
        db.rollback()

        print("CATEGORY ADD - MySQL ERROR:")
        print(e)

        flash(
            "Unable to add category. Please check the server console.",
            "error",
        )

    except Exception as e:
        db.rollback()

        print("CATEGORY ADD - ERROR:")
        print(e)

        flash(
            "Unable to add category.",
            "error",
        )

    finally:
        cursor.close()

    return redirect(url_for("admin_categories"))

@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_category(category_id):
    if request.method == "GET":
        category = next((c for c in fetch_categories() if c["id"] == category_id), None)
        if not category:
            flash("Category not found.", "error")
            return redirect(url_for("admin_categories"))
        return render_template("admin/edit_category.html", title="Edit Category", category=category)
    db = get_db()
    cursor = db.cursor()

    try:
        category_name = request.form.get("category_name", "").strip()
        icon = request.form.get("icon", "*").strip() or "*"
        description = request.form.get("description", "").strip()

        try:
            display_order = int(
                request.form.get("display_order", "0") or "0"
            )
        except (TypeError, ValueError):
            display_order = 0

        is_active = 1 if request.form.get("is_active") else 0

        if not category_name:
            flash("Category name is required.", "error")
            return redirect(url_for("admin_categories"))

        # Check whether another category already uses this name.
        cursor.execute(
            """
            SELECT id
            FROM categories
            WHERE category_name = %s
              AND id <> %s
            LIMIT 1
            """,
            (category_name, category_id),
        )

        existing_category = cursor.fetchone()

        if existing_category:
            flash(
                "Another category already uses this name.",
                "error",
            )
            return redirect(url_for("admin_categories"))

        cursor.execute(
            """
            UPDATE categories
            SET
                category_name = %s,
                icon = %s,
                description = %s,
                display_order = %s,
                is_active = %s
            WHERE id = %s
            """,
            (
                category_name,
                icon,
                description,
                display_order,
                is_active,
                category_id,
            ),
        )

        db.commit()

        flash("Category updated successfully.", "success")

    except mysql.connector.Error as e:
        db.rollback()

        print("CATEGORY EDIT - MySQL ERROR:")
        print(e)

        flash(
            "Unable to update category. Please check the server console.",
            "error",
        )

    except Exception as e:
        db.rollback()

        print("CATEGORY EDIT - ERROR:")
        print(e)

        flash(
            "Unable to update category.",
            "error",
        )

    finally:
        cursor.close()

    return redirect(url_for("admin_categories"))

@app.route("/admin/categories/<int:category_id>/toggle", methods=["POST"])
@admin_required
def toggle_category(category_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE categories SET is_active = NOT is_active WHERE id = %s", (category_id,))
    db.commit()
    flash("Category status updated.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS count FROM products WHERE category_id = %s", (category_id,))
    product_count = cursor.fetchone()["count"]
    if product_count:
        flash("This category contains products. Move the products to another category before deleting.", "error")
        return redirect(url_for("admin_categories"))

    cursor.execute("DELETE FROM categories WHERE id = %s", (category_id,))
    db.commit()
    flash("Category deleted.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/reorder", methods=["POST"])
@admin_required
def reorder_categories():
    db = get_db()
    cursor = db.cursor()
    category_ids = request.form.get("category_order", "")
    for index, category_id in enumerate([item for item in category_ids.split(",") if item.strip()], start=1):
        cursor.execute("UPDATE categories SET display_order = %s WHERE id = %s", (index, int(category_id)))
    db.commit()
    flash("Category order updated.", "success")
    return redirect(url_for("admin_categories"))


@app.route("/admin/categories/export/<export_type>")
@admin_required
def export_categories(export_type):
    # REPORT_REDESIGN_MARKER
    # Repurposed for Sales Analytics Report page + CSV export.
    if export_type == "excel":

        # Sales Analytics Report Excel export (CSV-compatible)
        date_filter = request.args.get("date_range", "last30")
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        category_id = request.args.get("category_id", type=int)
        product_id = request.args.get("product_id", type=int)
        payment_method = request.args.get("payment_method", "all")

        from datetime import datetime, date, timedelta

        def parse_ymd(s):
            if not s:
                return None
            return datetime.strptime(s, "%Y-%m-%d").date()

        today = date.today()

        if date_filter == "today":
            start_d = today
            end_d = today
        elif date_filter == "yesterday":
            start_d = today - timedelta(days=1)
            end_d = today - timedelta(days=1)
        elif date_filter == "last7":
            start_d = today - timedelta(days=6)
            end_d = today
        elif date_filter == "last30":
            start_d = today - timedelta(days=29)
            end_d = today
        elif date_filter == "current_month":
            start_d = today.replace(day=1)
            end_d = today
        elif date_filter == "prev_month":
            first_this_month = today.replace(day=1)
            last_prev_month = first_this_month - timedelta(days=1)
            start_d = last_prev_month.replace(day=1)
            end_d = last_prev_month
        elif date_filter == "current_year":
            start_d = today.replace(month=1, day=1)
            end_d = today
        elif date_filter == "custom":
            start_d = parse_ymd(start_date) or (today - timedelta(days=29))
            end_d = parse_ymd(end_date) or today
        else:
            start_d = today - timedelta(days=29)
            end_d = today

        start_dt = datetime.combine(start_d, datetime.min.time())
        end_dt = datetime.combine(end_d, datetime.max.time())

        pay_cond_sql = ""
        pay_params = []
        if payment_method and payment_method != "all":
            pay_cond_sql = " AND o.payment_method = %s"
            pay_params = [payment_method]

        cat_cond_sql = ""
        cat_params = []
        if category_id:
            cat_cond_sql = " AND p.category_id = %s"
            cat_params = [category_id]

        prod_cond_sql = ""
        prod_params = []
        if product_id:
            prod_cond_sql = " AND oi.product_id = %s"
            prod_params = [product_id]

        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute(
            f"""
            SELECT
              COALESCE(SUM(oi.line_total),0) AS revenue,
              COALESCE(SUM(oi.quantity),0) AS units,
              COUNT(DISTINCT o.id) AS orders
            FROM orders o
            JOIN order_items oi ON oi.order_id=o.id
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE o.created_at BETWEEN %s AND %s
              {pay_cond_sql}
              {cat_cond_sql}
              {prod_cond_sql}
            """,
            [start_dt, end_dt] + pay_params + cat_params + prod_params,
        )
        totals = cur.fetchone() or {}

        csv_lines = ["SECTION,ITEM1,ITEM2,ITEM3,ITEM4"]
        csv_lines.append(f"SUMMARY,total_revenue,{totals.get('revenue',0)},total_orders,{totals.get('orders',0)}")

        csv_lines.append("CATEGORY,category_name,units_sold,revenue")
        cur.execute(
            f"""
            SELECT
              COALESCE(c.category_name,'Uncategorized') AS category_name,
              SUM(oi.quantity) AS units_sold,
              SUM(oi.line_total) AS revenue
            FROM orders o
            JOIN order_items oi ON oi.order_id=o.id
            LEFT JOIN products p ON p.id=oi.product_id
            LEFT JOIN categories c ON c.id=p.category_id
            WHERE o.created_at BETWEEN %s AND %s
              {pay_cond_sql}
              {cat_cond_sql}
              {prod_cond_sql}
            GROUP BY COALESCE(c.category_name,'Uncategorized')
            ORDER BY revenue DESC
            """,
            [start_dt, end_dt] + pay_params + cat_params + prod_params,
        )
        for r in cur.fetchall() or []:
            csv_lines.append(
                f"CATEGORY,{r.get('category_name','')},{int(r.get('units_sold') or 0)},{float(r.get('revenue') or 0)}"
            )

        for row in rows:
            csv_lines.append(
                f"\"{row['category_name']}\",\"{row.get('description') or ''}\",{row['display_order']},{row['products_count']},{row['products_in_stock']},{row['products_out_of_stock']},{'Active' if row['is_active'] else 'Inactive'}"
            )
        response = make_response("\n".join(csv_lines))
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = "attachment; filename=category-report.csv"
        return response

    # Reports disabled
    return "Reports are disabled.", 403





@app.route("/admin/products")
@admin_required
def admin_products():
    category_id = request.args.get("category_id", type=int)
    return render_template(
        "admin/products.html",
        title="Products",
        products=fetch_products(active_only=False, category_id=category_id),
        categories=fetch_categories(active_only=False),
        selected_category_id=category_id,
    )


@app.route("/admin/discounts", methods=["GET", "POST"])
@admin_required
def admin_discounts():
    if request.method == "POST":
        try:
            discount = Decimal(request.form.get("discount_percentage", ""))
            if not discount.is_finite() or discount < 0 or discount > 100:
                raise ValueError
            if discount != money(discount):
                raise ValueError
            product_id = int(request.form.get("product_id", ""))
        except (InvalidOperation, ValueError):
            flash("Enter a discount percentage from 0 to 100 with up to two decimal places.", "error")
            return redirect(url_for("admin_discounts"))

        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT price FROM products WHERE id = %s FOR UPDATE", (product_id,))
            product = cursor.fetchone()
            if not product:
                db.rollback()
                flash("Product not found.", "error")
            else:
                cursor.execute("UPDATE products SET discount_percentage = %s WHERE id = %s", (money(discount), product_id))
                db.commit()
                flash("Product discount saved.", "success")
        finally:
            cursor.close()
        return redirect(url_for("admin_discounts"))

    return render_template("admin/discounts.html", title="Product Discounts", products=fetch_products(active_only=False))



@app.route("/admin/products/<int:product_id>/adjust-stock", methods=["POST"])
@admin_required
def adjust_stock(product_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT stock_quantity FROM products WHERE id = %s FOR UPDATE", (product_id,))
    product = cursor.fetchone()
    if not product:
        flash("Product not found.", "error")
        db.rollback()
        return redirect(url_for("admin_inventory"))

    try:
        delta = int(request.form.get("delta", ""))
        if delta not in (-1, 1):
            raise ValueError
    except ValueError:
        db.rollback()
        flash("Choose Add 1 or Reduce 1 to adjust stock.", "error")
        return redirect(url_for("admin_inventory"))
    current_stock = int(product.get("stock_quantity", 0) or 0)
    new_stock = min(2147483647, max(0, current_stock + delta))
    cursor.execute("UPDATE products SET stock_quantity = %s WHERE id = %s", (new_stock, product_id))
    db.commit()
    flash("Stock updated successfully.", "success")
    return redirect(url_for("admin_inventory"))


@app.route("/admin/inventory")
@admin_required
def admin_inventory():
    products = fetch_products(active_only=False)
    return render_template("admin/inventory.html", title="Inventory", products=products,
                           total_stock=sum(int(p.get("stock_quantity") or 0) for p in products),
                           out_of_stock=sum(get_stock_status(p)["label"] == "OUT OF STOCK" for p in products),
                           low_stock=sum(get_stock_status(p)["label"] == "LOW STOCK" for p in products))


@app.route("/admin/inventory/<int:product_id>/edit", methods=["POST"])
@admin_required
def edit_inventory(product_id):
    try:
        stock = int(request.form.get("stock_quantity", ""))
        limit = int(request.form.get("low_stock_limit", ""))
        if not (0 <= stock <= 2147483647 and 0 <= limit <= 2147483647):
            raise ValueError
    except ValueError:
        flash("Stock and low-stock alert must be non-negative whole numbers.", "error")
        return redirect(url_for("admin_inventory"))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM products WHERE id = %s FOR UPDATE", (product_id,))
    if not cursor.fetchone():
        db.rollback()
        flash("Product not found.", "error")
    else:
        cursor.execute("UPDATE products SET stock_quantity = %s, low_stock_limit = %s WHERE id = %s",
                       (stock, limit, product_id))
        db.commit()
        flash("Inventory updated.", "success")
    cursor.close()
    return redirect(url_for("admin_inventory"))


@app.route("/admin/products/add", methods=["POST"])
@admin_required
def add_product():
    db = get_db()
    cursor = db.cursor()

    image_url = None
    if "image" in request.files:
        image_file = request.files["image"]
        image_url = save_product_image(image_file)
        if image_file.filename and not image_url:
            return redirect(url_for("admin_products"))

    cursor.execute(
        """
        INSERT INTO products (name, price, description, image_url, category_id)
        VALUES (%s, %s, %s, %s, %s)
        """,

        (
            request.form["name"].strip(),
            request.form["price"],
            request.form.get("description", "").strip(),
            image_url,
            request.form.get("category_id") or None,
        ),
    )
    db.commit()
    flash("Product added. Set its opening stock on the Inventory page.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):
    if request.method == "GET":
        products = fetch_products(active_only=False)
        product = next((p for p in products if p["id"] == product_id), None)
        if not product:
            flash("Product not found.", "error")
            return redirect(url_for("admin_products"))
        return render_template("admin/edit_product.html", title="Edit Product", product=product,
                               categories=fetch_categories(active_only=False))

    db = get_db()
    cursor = db.cursor()

    # Get current product image
    cursor.execute(
        "SELECT image_url FROM products WHERE id = %s",
        (product_id,)
    )

    result = cursor.fetchone()
    if not result:
        flash("Product not found.", "error")
        return redirect(url_for("admin_products"))
    image_url = result[0]

    # Handle new image upload
    # Upload new image (keeps existing if no new file is selected)
    if "image" in request.files:
        image_file = request.files["image"]
        if image_file and image_file.filename != "":
            new_image_url = save_product_image(image_file)
            if not new_image_url:
                return redirect(url_for("edit_product", product_id=product_id))
            image_url = new_image_url

    # Remove existing image (set to NULL) when requested
    if request.form.get("remove_image") == "1":
        image_url = None



    category_id = request.form.get("category_id") or None

    cursor.execute(
        """
        UPDATE products
        SET
            name = %s,
            price = %s,
            description = %s,
            image_url = %s,
            category_id = %s,
            is_active = %s
        WHERE id = %s
        """,
        (
            request.form["name"].strip(),
            request.form["price"],
            request.form.get("description", "").strip(),
            image_url,
            category_id,
            1 if request.form.get("is_active") else 0,
            product_id,
        ),
    )

    db.commit()

    flash("Product updated successfully.", "success")

    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def delete_product(product_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
    db.commit()
    flash("Product deleted successfully.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")
    query = "SELECT id, created_at, customer_name, phone, email, total_amount, payment_method, payment_status FROM orders"
    conditions, params = [], []
    if search:
        conditions.append("(CAST(id AS CHAR) LIKE %s OR customer_name LIKE %s OR phone LIKE %s OR email LIKE %s)")
        params.extend([f"%{search}%"] * 4)
    if status in ("Paid", "Pending", "Cancelled"):
        conditions.append("payment_status = %s")
        params.append(status)
    else:
        status = "all"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"
    cursor.execute(query, tuple(params))
    orders = cursor.fetchall()
    return render_template("admin/orders.html", title="Orders", orders=orders, search=search, status=status)


@app.route("/admin/reset-reports", methods=["POST"])
@admin_required
def reset_reports():
    confirm = request.form.get("confirm", "")
    typed = (request.form.get("typed_confirm") or "").strip().upper()

    # Require explicit reconfirmation
    if confirm != "YES" or typed != "RESET":
        flash("Reset cancelled. Please type RESET to confirm.", "error")
        return redirect(request.referrer or url_for("admin_dashboard"))

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM order_items")
    cursor.execute("DELETE FROM orders")
    db.commit()
    flash("Reports reset successfully (orders & revenue cleared).", "success")
    return redirect(url_for("admin_dashboard"))




@app.route("/admin/orders/<int:order_id>/cancel", methods=["POST"])
@admin_required
def cancel_order(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, payment_status FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin_orders"))

    cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = %s", (order_id,))
    items = cursor.fetchall()
    for item in items:
        if item.get("product_id"):
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity + %s WHERE id = %s",
                (item.get("quantity", 0), item.get("product_id")),
            )

    cursor.execute("UPDATE orders SET payment_status = %s WHERE id = %s", ("Cancelled", order_id))
    db.commit()
    flash("Order cancelled and stock restored.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/<int:order_id>/bill")
@admin_required
def admin_bill(order_id):
    order, items = get_order_with_items(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin_orders"))
    return render_template("admin/bill.html", order=order, items=items)


@app.route('/service-worker.js')
def service_worker():
    return send_from_directory(os.path.join(app.static_folder, 'sw'), 'customer-service-worker.js', mimetype='application/javascript')


@app.route('/admin-service-worker.js')
def admin_service_worker():
    return send_from_directory(os.path.join(app.static_folder, 'sw'), 'admin-service-worker.js', mimetype='application/javascript')


@app.route('/manifest.json')
def manifest_customer():
    return send_from_directory(app.static_folder, 'manifest-customer.json', mimetype='application/manifest+json')


@app.route('/admin/manifest.json')
def manifest_admin():
    return send_from_directory(app.static_folder, 'manifest-admin.json', mimetype='application/manifest+json')


@app.route('/manifest-customer.json')
def manifest_customer_alias():
    return manifest_customer()


@app.route('/manifest-admin.json')
def manifest_admin_alias():
    return manifest_admin()



def get_order_with_items(order_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()
    if not order:
        return None, []

    cursor.execute("SELECT * FROM order_items WHERE order_id = %s", (order_id,))
    return order, cursor.fetchall()


def build_bill_message(order, items):
    lines = [
        f"{shop_details()['name']} Bill #{order['id']}",
        f"Customer: {order['customer_name']}",
        f"Total: Rs. {order['total_amount']}",
        "Items:",
    ]
    for item in items:
        lines.append(f"{item['product_name']} x {item['quantity']} = Rs. {item['line_total']}")
    return "\n".join(lines)






with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
