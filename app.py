import os
import smtplib
from decimal import Decimal
from email.message import EmailMessage
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

from database import close_db, get_db, init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
app.teardown_appcontext(close_db)


def shop_details():
    return {
        "name": os.getenv("SHOP_NAME", "Crackers Hub"),
        "phone": os.getenv("SHOP_PHONE", "9876543210"),
        "email": os.getenv("SHOP_EMAIL", "admin@crackershub.local"),
        "address": os.getenv("SHOP_ADDRESS", "Main Road, Sivakasi, Tamil Nadu"),
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


def fetch_products(active_only=True):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if active_only:
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
    else:
        cursor.execute("SELECT * FROM products ORDER BY is_active DESC, name")
    return cursor.fetchall()


@app.route("/")
def home():
    return render_template("customer/home.html")


@app.route("/about")
def about():
    return render_template("customer/about.html")


@app.route("/gift-box")
def gift_box():
    return render_template("customer/gift_box.html")


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
        notification = send_bill_notifications(order_id)
        if notification["email_sent"]:
            flash(
                "Order placed successfully. The bill was emailed automatically. You can send it to WhatsApp from the bill page.",
                "success",
            )
        elif notification["email_reason"] == "not_configured":
            flash(
                "Order placed successfully. Email auto-send is missing SMTP settings, so the bill is ready here.",
                "error",
            )
        else:
            flash(
                "Order placed successfully. Email auto-send failed. Check your Gmail app password and SMTP settings.",
                "error",
            )
        return redirect(url_for("customer_bill", order_id=order_id))

    return render_template("customer/checkout.html", cart=cart, total=total)


@app.route("/bill/<int:order_id>")
def customer_bill(order_id):
    order, items = get_order_with_items(order_id)
    if not order:
        flash("Bill not found.", "error")
        return redirect(url_for("customer_products"))

    whatsapp_message = build_bill_message(order, items)
    return render_template(
        "customer/bill.html",
        order=order,
        items=items,
        whatsapp_message=whatsapp_message,
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
    cursor.execute(
        """
        INSERT INTO products (name, price, offer_percentage, description)
        VALUES (%s, %s, %s, %s)
        """,
        (
            request.form["name"].strip(),
            request.form["price"],
            request.form["offer_percentage"],
            request.form.get("description", "").strip(),
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
    cursor.execute(
        """
        UPDATE products
        SET name = %s, price = %s, offer_percentage = %s, description = %s, is_active = %s
        WHERE id = %s
        """,
        (
            request.form["name"].strip(),
            request.form["price"],
            request.form["offer_percentage"],
            request.form.get("description", "").strip(),
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
    cursor.execute("UPDATE products SET is_active = 0 WHERE id = %s", (product_id,))
    db.commit()
    flash("Product removed from customer listing.", "success")
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


def send_bill_notifications(order_id):
    order, items = get_order_with_items(order_id)
    if not order:
        return {"email_sent": False, "email_reason": "missing_order"}

    message = build_bill_message(order, items)
    email_result = send_email_bill(order["email"], f"{shop_details()['name']} Bill #{order['id']}", message)
    return {"email_sent": email_result["sent"], "email_reason": email_result["reason"]}


def send_email_bill(to_email, subject, message):
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user).strip()
    from_name = os.getenv("SMTP_FROM_NAME", shop_details()["name"]).strip()

    if not smtp_host or not smtp_user or not smtp_password or not from_email:
        print(f"EMAIL AUTO-SEND SKIPPED: SMTP credentials not configured.\nTO {to_email}\n{message}")
        return {"sent": False, "reason": "not_configured"}

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = f"{from_name} <{from_email}>"
    email["To"] = to_email
    email.set_content(message)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(email)
        return {"sent": True, "reason": "sent"}
    except (OSError, smtplib.SMTPException) as error:
        print(f"EMAIL AUTO-SEND FAILED: {error}")
        return {"sent": False, "reason": "failed"}


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
