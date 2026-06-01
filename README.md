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
