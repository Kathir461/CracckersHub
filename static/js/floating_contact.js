(function () {
  // Wait for DOM
  document.addEventListener('DOMContentLoaded', () => {
    const shopPhone = (window.SHOP_PHONE || '').trim();
    if (!shopPhone) return;

    // Build WhatsApp and phone links
    const normalized = shopPhone.replace(/\s+/g, '');
    const waLink = `https://wa.me/${normalized}`;
    const phoneLink = `tel:${normalized}`;

    const waIcon = document.getElementById('floating-whatsapp');
    const phoneIcon = document.getElementById('floating-phone');

    if (waIcon) waIcon.href = waLink;
    if (phoneIcon) phoneIcon.href = phoneLink;
  });
})();

