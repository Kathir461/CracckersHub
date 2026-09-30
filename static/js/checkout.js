const paymentMethod = document.querySelector("#payment-method");
const gpayBox = document.querySelector("#gpay-box");
const cardBox = document.querySelector("#card-box");

function updatePaymentBox() {
  const isCard = paymentMethod.value === "card";
  if (cardBox) cardBox.classList.toggle("hidden", !isCard);
  if (gpayBox) gpayBox.classList.toggle("hidden", isCard);
}

if (paymentMethod) {
  paymentMethod.addEventListener("change", updatePaymentBox);
  updatePaymentBox();
}
