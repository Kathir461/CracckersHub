const rows = document.querySelectorAll(".product-row[data-price]");
const grandTotal = document.querySelector("#grand-total");

function formatRupees(value) {
  return `Rs. ${value.toFixed(2)}`;
}

function isRowVisible(row){
  const rect = row.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function calculateTotals({onlyVisible} = { onlyVisible: false }) {
  let total = 0;

  rows.forEach((row) => {
    const price = Number(row.dataset.price);
    const input = row.querySelector(".quantity-input");
    const quantity = Math.max(0, Number(input.value || 0));
    const lineTotal = price * quantity;

    const lineCell = row.querySelector(".line-total");
    if(lineCell) lineCell.textContent = formatRupees(lineTotal);

    if (!onlyVisible || isRowVisible(row)) {
      total += lineTotal;
    }
  });

  if (grandTotal) grandTotal.textContent = formatRupees(total);
  return total;
}

function updateShopTotalsForVisibleRows(){
  calculateTotals({ onlyVisible: true });
}

window.__updateShopTotalsForVisibleRows = updateShopTotalsForVisibleRows;

rows.forEach((row) => {
  const input = row.querySelector(".quantity-input");
  if(!input) return;
  input.addEventListener("input", () => calculateTotals({ onlyVisible: false }));
});

calculateTotals({ onlyVisible: false });

