# Crackers Hub E-Commerce Website

A Flask, HTML, CSS, JavaScript, and MySQL project for a crackers shop with customer ordering and admin management.

## Features

- Customer product listing in table format with SNO, product name, price, offer percentage, quantity, and final price.
- Checkout with GPay or card option.
- Customer bill view, printable bill, order history lookup, and admin contact details.
- Admin login, product add/edit/delete, customer order list, and printable bill generation.
- MySQL database tables are created automatically on first run.

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

## Default Admin Login

- Username: `admin`
- Password: `admin123`

Change these in `.env` before using the project seriously.

## Bill Delivery

After checkout, the app generates the bill and automatically emails it when SMTP credentials are configured in `.env`. The customer can send the bill to WhatsApp manually from the bill page. Without SMTP credentials, the order still succeeds and the bill remains available on the website.
