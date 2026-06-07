document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('form.table-panel');
  if (!form) return;

  const pending = sessionStorage.getItem('pending_cart');
  if (!pending) return;

  let cart = [];
  try {
    cart = JSON.parse(pending) || [];
  } catch (e) {
    cart = [];
  }

  const byId = new Map();
  const byName = new Map();

  cart.forEach((item) => {
    if (!item) return;
    if (item.product_id != null) byId.set(String(item.product_id), item);
    if (item.name) byName.set(String(item.name).trim().toLowerCase(), item);
  });

  const rows = document.querySelectorAll('.product-table tbody tr[data-product-id]');

  rows.forEach((row) => {
    const input = row.querySelector('.quantity-input');
    if (!input) return;

    // Try by product id first (if we have it)
    const pid = row.dataset.productId != null ? String(row.dataset.productId) : null;
    let item = pid ? byId.get(pid) : undefined;

    // Fallback: try by product name (checkout summary stores only name)
    if (!item) {
      const nameEl = row.querySelector('td:nth-child(3) strong');
      const name = nameEl ? String(nameEl.textContent || '').trim().toLowerCase() : '';
      if (name) item = byName.get(name);
    }

    const qty = item && typeof item.quantity !== 'undefined' ? Number(item.quantity) : 0;
    input.value = Number.isFinite(qty) && qty > 0 ? qty : 0;

    // Trigger totals recalculation
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });

  // Clear after restore
  sessionStorage.removeItem('pending_cart');
});


