# TODO - Performance (Admin)

## Phase A — Must do first (safety + measurements)
- [x] Disable heavy fireworks animation on `/admin/*` pages (client-side CPU hog)
- [ ] Add performance logging for admin routes (timings per query + total request)


## Phase B — Database speedups (biggest server wins)
- [ ] Add MySQL indexes:
  - order_items(order_id)
  - order_items(product_id)
  - orders(created_at)
  - products(category_id, is_active)
  - products(stock_quantity)
  - categories(is_active, display_order)
- [ ] Update `database.py` to create indexes if missing

## Phase C — Query improvements
- [ ] Replace `SELECT *` in admin orders/products with explicit columns
- [ ] Merge multiple COUNT/SUM queries in admin dashboard into fewer queries
- [ ] Use pagination/LIMIT on admin products + admin orders

## Phase D — Caching + lazy loading
- [ ] Dashboard caching (60s) for admin dashboard route
- [ ] Lazy load sales report sections using AJAX (optional but recommended)

## Phase E — Verification
- [ ] Run `python -m py_compile app.py database.py`
- [ ] Test load times:
  - `/admin` < 1s
  - `/admin/products` < 1s
  - `/admin/orders` < 1s
  - `/admin/sales-details` < 2s

