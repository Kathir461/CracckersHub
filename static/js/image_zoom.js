// Image zoom modal for product images (customer + admin)

(function () {
  function ensureModal() {
    let modal = document.getElementById('imageZoomModal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'imageZoomModal';
    modal.className = 'image-zoom-modal hidden';

    modal.innerHTML = `
      <div class="image-zoom-backdrop" data-close-zoom="1"></div>
      <div class="image-zoom-dialog" role="dialog" aria-modal="true" aria-label="Image preview">
        <button type="button" class="image-zoom-close" aria-label="Close">&times;</button>
        <img class="image-zoom-img" src="" alt="Zoomed image">
      </div>
    `;

    document.body.appendChild(modal);
    return modal;
  }

  function openZoom(src, altText) {
    const modal = ensureModal();
    const img = modal.querySelector('.image-zoom-img');
    img.src = src;
    img.alt = altText || 'Image preview';

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    // focus close button for accessibility
    const closeBtn = modal.querySelector('.image-zoom-close');
    if (closeBtn) closeBtn.focus();
  }

  function closeZoom() {
    const modal = ensureModal();
    modal.classList.add('hidden');
    document.body.style.overflow = '';

    const img = modal.querySelector('.image-zoom-img');
    if (img) img.src = '';
  }

  function setup() {
    const zoomImages = document.querySelectorAll('.zoomable-image[data-full-image-url]');
    if (!zoomImages || zoomImages.length === 0) return;

    zoomImages.forEach((img) => {
      img.addEventListener('click', (e) => {
        e.preventDefault();
        const src = img.getAttribute('data-full-image-url') || img.src;
        const alt = img.getAttribute('alt');
        openZoom(src, alt);
      });
    });

    const modal = ensureModal();

    modal.addEventListener('click', (e) => {
      const closeOnBackdrop = e.target && e.target.getAttribute && e.target.getAttribute('data-close-zoom') === '1';
      const isCloseBtn = e.target && e.target.classList && e.target.classList.contains('image-zoom-close');
      if (closeOnBackdrop || isCloseBtn) closeZoom();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        const modalNow = document.getElementById('imageZoomModal');
        if (modalNow && !modalNow.classList.contains('hidden')) closeZoom();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();

