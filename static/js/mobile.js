document.querySelectorAll('.mobile-menu-toggle').forEach((button) => {
  const nav = document.getElementById(button.getAttribute('aria-controls'));
  if (!nav) return;
  nav.classList.add('collapsible-navigation');
  const container = button.parentElement;
  container.classList.add('navigation-ready');
  button.classList.add('ready');
  const close = () => {
    nav.classList.remove('menu-open');
    container.classList.remove('navigation-open');
    button.setAttribute('aria-expanded', 'false');
  };
  button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    nav.classList.toggle('menu-open', open);
    container.classList.toggle('navigation-open', open);
    button.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      close();
      button.focus();
    }
  });
  nav.querySelectorAll('a').forEach((link) => {
    if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
  });
});

// Label report and admin rows using their actual column headings on small screens.
document.querySelectorAll('.admin-table, .mobile-cards').forEach((table) => {
  table.classList.add('mobile-cards');
  const headings = Array.from(table.querySelectorAll('thead tr:first-child th')).map((th) => th.textContent.trim());
  table.querySelectorAll('tbody tr').forEach((row) => {
    Array.from(row.cells).forEach((cell, index) => {
      if (cell.colSpan === 1 && !cell.dataset.label && headings[index]) cell.dataset.label = headings[index];
    });
  });
});
