document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('continue-shopping');
  if (!btn) return;

  btn.addEventListener('click', () => {
    // Persist cart from checkout summary (reliable) 
    // Checkout page should behave like a cart page.
    // We read quantities from the order summary rendered on checkout.
    let cart = window.__CURRENT_CART__;

    // Always rebuild from checkout summary first.
    try {
      const summary = document.querySelectorAll('.summary-card .summary-row');
      if (summary && summary.length > 0) {
        cart = [];
        summary.forEach((row) => {
          const left = row.querySelector('span');
          if (!left) return;

          const text = (left.textContent || '').trim();
          // Expect: "Product Name x qty"
          const parts = text.split(' x ');
          const name = parts[0] || '';
          const qtyStr = parts[1] || '0';
          const qty = Math.max(0, parseInt(qtyStr, 10) || 0);
          if (qty > 0) cart.push({ product_id: null, name, quantity: qty });
        });
      }
    } catch (e) {
      // ignore
    }

    // Fallback: if cart is still empty, try to read quantities from products table.
    if (!cart || !Array.isArray(cart) || cart.length === 0) {

      try {
        const table = document.querySelector('.product-table');
        if (table) {
          cart = [];
          const rows = table.querySelectorAll('tbody tr[data-price]');
          rows.forEach((row) => {
            const input = row.querySelector('.quantity-input');
            const quantity = Math.max(0, parseInt(input?.value || '0', 10) || 0);
            if (quantity > 0) {
              cart.push({ product_id: row.dataset.productId, quantity });
            }
          });
        }
      } catch (e) {
        cart = [];
      }
    }

    cart = cart || [];

    try {
      sessionStorage.setItem('pending_cart', JSON.stringify(cart));
    } catch (e) {}

    // Go back to shop page (backend will also restore if server-side cart exists)
    window.location.href = window.CONTINUE_SHOP_URL || '/products';
  });
});


