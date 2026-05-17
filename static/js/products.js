const rows = document.querySelectorAll(".product-table tbody tr[data-price]");
const grandTotal = document.querySelector("#grand-total");

function formatRupees(value) {
  return `Rs. ${value.toFixed(2)}`;
}

function calculateTotals() {
  let total = 0;
  rows.forEach((row) => {
    const price = Number(row.dataset.price);
    const offer = Number(row.dataset.offer);
    const input = row.querySelector(".quantity-input");
    const quantity = Math.max(0, Number(input.value || 0));
    const discountedPrice = price * (1 - offer / 100);
    const lineTotal = discountedPrice * quantity;
    row.querySelector(".line-total").textContent = formatRupees(lineTotal);
    total += lineTotal;
  });
  grandTotal.textContent = formatRupees(total);
}

rows.forEach((row) => {
  row.querySelector(".quantity-input").addEventListener("input", calculateTotals);
});

calculateTotals();
