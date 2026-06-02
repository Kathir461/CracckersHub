import os
import time
from decimal import Decimal
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from database import close_db, get_db, init_db

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
    """Save uploaded image and return the URL path."""
    if not image_file or image_file.filename == "":
        return None

    if not allowed_file(image_file.filename):
        flash("Only image files (PNG, JPG, JPEG, GIF, WebP) are allowed.", "error")
        return None

    try:
        # Check file size if content_length is available
        if hasattr(image_file, 'content_length') and image_file.content_length and image_file.content_length > MAX_FILE_SIZE:
            flash("File size exceeds 5MB limit.", "error")
            return None
    except Exception as e:
        print(f"Error checking file size: {e}")

    try:
        filename = secure_filename(image_file.filename)
        # Add timestamp to make filename unique
        filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        image_file.save(filepath)
        return f"/static/uploads/{filename}"
    except Exception as e:
        flash(f"Error uploading image: {str(e)}", "error")
        print(f"Image upload error: {e}")
        return None


def shop_details():
    return {
        "name": os.getenv("SHOP_NAME", "Cracckers Hub"),
        "phone": os.getenv("SHOP_PHONE", "8248627753"),
        "email": os.getenv("SHOP_EMAIL", "cracckershubsivakasi@gmail.com"),
        "address": os.getenv("SHOP_ADDRESS", "No - 3 , balan nagar , Aduthurai , Thanjavur district. 612101"),
    }


@app.context_processor
def inject_globals():
    return {"shop": shop_details()}


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


def fetch_products(active_only=True, category=None):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM products"
    conditions = []
    params = []

    if active_only:
        conditions.append("is_active = 1")
    if category:
        conditions.append("product_category = %s")
        params.append(category)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY name"
    cursor.execute(query, tuple(params))
    return cursor.fetchall()



@app.route("/")
def home():
    return render_template("customer/home.html")


@app.route("/about")
def about():
    return render_template("customer/about.html")










@app.route("/gift-box", methods=["GET", "POST"])
def gift_box():
    # Gift box page uses the same interactive table + checkout flow as the shop.
    products = fetch_products(active_only=True)

    if request.method == "POST":
        selected_items = []
        for product in products:
            quantity_raw = request.form.get(f"quantity_{product['id']}", "0")
            try:
                quantity = int(quantity_raw)
            except ValueError:
                quantity = 0

            if quantity > 0:
                price = money(product["price"])
                offer = Decimal(str(product["offer_percentage"]))
                discounted_price = money(price * (Decimal("1") - offer / Decimal("100")))
                selected_items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "price": str(price),
                        "offer_percentage": str(offer),
                        "quantity": quantity,
                        "line_total": str(money(discounted_price * quantity)),
                    }
                )

        if not selected_items:
            flash("Enter quantity for at least one product.", "error")
            return redirect(url_for("gift_box"))

        session["cart"] = selected_items
        return redirect(url_for("checkout"))

    return render_template("customer/gift_box.html", products=products)


@app.route("/products", methods=["GET", "POST"])
def customer_products():
    products = fetch_products(active_only=True)
    if request.method == "POST":
        selected_items = []
        for product in products:
            quantity_raw = request.form.get(f"quantity_{product['id']}", "0")
            try:
                quantity = int(quantity_raw)
            except ValueError:
                quantity = 0

            if quantity > 0:
                price = money(product["price"])
                offer = Decimal(str(product["offer_percentage"]))
                discounted_price = money(price * (Decimal("1") - offer / Decimal("100")))
                selected_items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "price": str(price),
                        "offer_percentage": str(offer),
                        "quantity": quantity,
                        "line_total": str(money(discounted_price * quantity)),
                    }
                )

        if not selected_items:
            flash("Enter quantity for at least one product.", "error")
            return redirect(url_for("customer_products"))

        session["cart"] = selected_items
        return redirect(url_for("checkout"))

    return render_template("customer/products.html", products=products)


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", [])
    if not cart:
        flash("Your cart is empty.", "error")
        return redirect(url_for("customer_products"))

    total = sum(Decimal(item["line_total"]) for item in cart)

    if request.method == "POST":
        customer_name = request.form["customer_name"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()
        address = request.form["address"].strip()
        payment_method = request.form["payment_method"]

        if not customer_name or not phone or not email or not address:
            flash("Please fill all customer details.", "error")
            return render_template("customer/checkout.html", cart=cart, total=total)

        db = get_db()
        cursor = db.cursor()
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
                    item["offer_percentage"],
                    item["quantity"],
                    item["line_total"],
                ),
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
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS count FROM products WHERE is_active = 1")
    product_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COUNT(*) AS count FROM orders")
    order_count = cursor.fetchone()["count"]
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) AS total FROM orders")
    sales_total = cursor.fetchone()["total"]
    return render_template(
        "admin/dashboard.html",
        product_count=product_count,
        order_count=order_count,
        sales_total=sales_total,
    )


@app.route("/admin/products")
@admin_required
def admin_products():
    return render_template("admin/products.html", products=fetch_products(active_only=False))


@app.route("/admin/products/add", methods=["POST"])
@admin_required
def add_product():
    db = get_db()
    cursor = db.cursor()

    image_url = None
    if "image" in request.files:
        image_file = request.files["image"]
        image_url = save_product_image(image_file)

    cursor.execute(
        """
        INSERT INTO products (name, price, offer_percentage, description, image_url, product_category)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,

        (
            request.form["name"].strip(),
            request.form["price"],
            request.form["offer_percentage"],
            request.form.get("description", "").strip(),
            image_url,
            request.form.get("product_category", "shop"),
        ),
    )
    db.commit()
    flash("Product added.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/products/<int:product_id>/edit", methods=["POST"])
@admin_required
def edit_product(product_id):
    db = get_db()
    cursor = db.cursor()

    # Get current product to preserve image if not updated
    cursor.execute("SELECT image_url FROM products WHERE id = %s", (product_id,))
    result = cursor.fetchone()
    image_url = result[0] if result else None

    # Handle new image upload
    if "image" in request.files:
        image_file = request.files["image"]
        if image_file and image_file.filename != "":
            new_image_url = save_product_image(image_file)
            if new_image_url:
                image_url = new_image_url

    # category can be missing/empty for older templates; fallback to shop
    product_category = request.form.get("product_category") or "shop"

    cursor.execute(
        """
        UPDATE products
        SET name = %s, price = %s, offer_percentage = %s, description = %s, image_url = %s, product_category = %s, is_active = %s
        WHERE id = %s
        """
        (
            request.form["name"].strip(),
            request.form["price"],
            request.form["offer_percentage"],
            request.form.get("description", "").strip(),
            image_url,
            product_category,
            1 if request.form.get("is_active") else 0,
            product_id,
        ),
    )
    db.commit()
    flash("Product updated.", "success")
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
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
    orders = cursor.fetchall()
    return render_template("admin/orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/bill")
@admin_required
def admin_bill(order_id):
    order, items = get_order_with_items(order_id)
    if not order:
        flash("Order not found.", "error")
        return redirect(url_for("admin_orders"))
    return render_template("admin/bill.html", order=order, items=items)


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
