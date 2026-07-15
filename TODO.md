# TODO - Sales Analytics Report Redesign

## Step 1: Route/Template mapping
- Update `app.py` route `/admin/categories/export/<export_type>` to serve the new **Sales Analytics Report** page and exports.

## Step 2: Implement backend report data
- Add helper functions in `app.py` to compute (for selected date range):
  - Summary cards + growth % vs previous period
  - Category report dataset
  - Product report dataset (units sold, revenue, discount stats, stock statuses)
  - Daily / weekly / monthly / yearly aggregates
  - Chart data (Chart.js)
  - Inventory report dataset
  - Best/low sellers top/bottom 10
  - Customer analytics

## Step 3: Build export handlers
- Export PDF: reuse browser print-to-PDF by returning the redesigned report HTML with print styles (or implement as download HTML).
- Export Excel: return a CSV (or XLSX if later added) built from the report tables.

## Step 4: Redesign template
- Replace `templates/admin/category_report.html` with new Sales Analytics Report UI:
  - Top summary cards
  - Filter section (today/yesterday/last7/last30/current month/prev month/current year/custom)
  - Charts (Chart.js)
  - Tables (category, product, daily, weekly, monthly, yearly, inventory, best sellers, low sellers, customer analytics)
  - Print-friendly layout (hide sidebar/nav)

## Step 5: CSS updates
- Extend `static/css/admin.css` with:
  - report-specific spacing
  - print media rules: landscape A4, hide sidebar, repeat table headers.

## Step 6: Wire DataTables (optional)
- Add DataTables initialization for large tables if already included in base template.

## Step 7: Verification
- Run `python -m py_compile app.py`
- Load the report page and test:
  - filters work
  - charts render
  - exports download
  - print preview looks correct

