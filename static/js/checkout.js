const paymentMethod = document.querySelector("#payment-method");
const gpayBox = document.querySelector("#gpay-box");
const cardBox = document.querySelector("#card-box");

function updatePaymentBox() {
  const isCard = paymentMethod.value === "card";
  cardBox.classList.toggle("hidden", !isCard);
  gpayBox.classList.toggle("hidden", isCard);
}

paymentMethod.addEventListener("change", updatePaymentBox);
updatePaymentBox();
