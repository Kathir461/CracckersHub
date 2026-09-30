# Crackers Hub E-Commerce Website

A Flask, HTML, CSS, JavaScript, and MySQL project for a crackers shop with customer ordering and admin management.

## Features

- Customer product listing with original prices crossed out when discounted, selling prices, quantities, and totals.
- Admin Discounts page for percentage discounts per product; discounted prices apply to carts, checkout, and bills.
- Checkout with GPay or card option.
- Customer bill view, printable bill, order history lookup, and admin contact details.
- Admin login, product add/edit/delete, customer order list, and printable bill generation.
- MySQL database tables are created automatically on first run.

## Product discounts

Open **Admin > Discounts**, enter a percentage, and click **Save Discount** for that product. For example, a 20% discount on Rs. 250 shows the original Rs. 250 crossed out and a selling price of Rs. 200. Set the percentage to 0 to remove it. Discounts must be between 0 and 100, with at most two decimal places. Selling prices are calculated as `price * (1 - discount_percentage / 100)` and rounded to the nearest paise (half up) before multiplying by quantity.

Restart the app after updating: startup adds the `products.discount_percentage` column automatically. Earlier rupee discounts, if present, are converted once to equivalent percentages rounded to two decimal places; review those discounts since rounding may slightly change selling prices. Products without discounts default to 0%. The database user needs permission to alter the table. Changing the original price keeps the saved percentage. Existing carts refresh their prices at checkout; previously placed orders retain their recorded prices.

## Products, inventory, and images

- **Products** lists photos, product details, categories, original prices, and visibility. Use **Edit Product** to change details or replace a photo.
- **Inventory** manages quantities, low-stock alert thresholds, and quick +1/-1 adjustments. New products start with zero stock; editing product details preserves inventory and discounts.
- Missing images show an "Image unavailable" placeholder. A saved URL cannot restore a missing file: re-upload the original photo from **Edit Product**.
- For hosted deployments, configure `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` (or `CLOUDINARY_URL`) for durable image storage. `CLOUDINARY_UPLOAD_PRESET` is optional for signed uploads. Upload failures are shown instead of silently saving temporary local files.
- Without Cloudinary, uploads use `static/uploads`; this directory must persist across server restarts and deployments. The optional `migrate_images_cloudinary.py` script can move existing local files to Cloudinary after its three credentials are configured.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and update your MySQL username/password.
4. Make sure MySQL server is running.
5. Start the app:

```bash
python app.py
```

6. Open `http://127.0.0.1:5000`.

## Railway Deployment

This repo includes a `Procfile` for Railway:

```bash
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

In Railway, add the environment variables from `.env.example` in the service settings. Do not upload `.env` because it contains real passwords.

## Default Admin Login

- Username: `admin`
- Password: `admin123`

Change these in `.env` before using the project seriously.

## Bill Delivery

After checkout, the app generates the bill and displays it on the website. The customer can view and print the bill directly from the bill page.

## Responsive admin and storefront

Categories use a compact list with a separate edit page; change display order in that form. Orders support searches by order number, customer, phone, or email and a payment-status filter. On phones, admin tables and shopping rows become labeled cards, with a collapsible navigation menu and larger form controls. Bills retain a scrollable item table on screen and a normal table when printed.
