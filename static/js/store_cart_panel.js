(function () {
  const grandTotalEl = document.querySelector('#grand-total');
  if (!grandTotalEl) return;

  const table = document.querySelector('.product-table');
  if (!table) return;

  const panel = document.createElement('div');
  panel.className = 'store-cart-panel hidden';
  panel.innerHTML = `
    <div class="store-cart-inner">
      <div class="store-cart-left">
        <div class="store-cart-items"><strong id="store-cart-count">0</strong> items</div>
        <div class="store-cart-total">Total: <strong id="store-cart-amount">Rs. 0.00</strong></div>
      </div>
      <div class="store-cart-right">
        <button class="button" type="button" id="store-cart-checkout">Checkout</button>
      </div>
    </div>
  `;

  document.body.appendChild(panel);

  const countEl = panel.querySelector('#store-cart-count');
  const amountEl = panel.querySelector('#store-cart-amount');
  const checkoutBtn = panel.querySelector('#store-cart-checkout');

  function formatRupees(value) {
    return `Rs. ${value.toFixed(2)}`;
  }

  function computeCart() {
    const rows = table.querySelectorAll('tbody tr[data-price]');
    let count = 0;
    let total = 0;

    rows.forEach((row) => {
      const input = row.querySelector('.quantity-input');
      const quantity = Math.max(0, parseInt(input?.value || '0', 10) || 0);
      const price = Number(row.dataset.price || 0);

      count += quantity;
      total += price * quantity;
    });

    return { count, total };
  }

  function showOrHide() {
    const { count, total } = computeCart();

    if (count > 0) {
      panel.classList.remove('hidden');
      countEl.textContent = String(count);
      amountEl.textContent = formatRupees(total);
    } else {
      panel.classList.add('hidden');
    }
  }

  // Sync panel on input changes (quantity inputs)
  const qtyInputs = table.querySelectorAll('.quantity-input');
  qtyInputs.forEach((input) => {
    input.addEventListener('input', showOrHide);
  });

  // Initial state
  showOrHide();

  checkoutBtn.addEventListener('click', () => {
    const form = table.closest('form');
    if (!form) return;

    const { count } = computeCart();
    if (count <= 0) return;

    // Submit form
    form.requestSubmit();
  });
})();

