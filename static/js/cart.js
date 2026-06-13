/* ============================================================
   Cart page — renders line items from vaiCart, handles qty/remove,
   promo codes, summary math, "free delivery above ₹999" progress.
   ============================================================ */

(function () {
  'use strict';

  const FREE_SHIPPING_THRESHOLD = 999;
  const SHIPPING_FEE = 49;

  const PROMO_CODES = {
    'VAISHNAVI10': { type: 'pct',  value: 10, label: '10% off' },
    'FIRSTORDER':  { type: 'flat', value: 100, label: '₹100 off' },
    'GAUSEVA':     { type: 'pct',  value: 5,  label: '5% off · supports cow welfare' },
  };

  const PROMO_KEY = 'vai_promo_v1';

  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  function getPromo() {
    try { return JSON.parse(localStorage.getItem(PROMO_KEY)); }
    catch { return null; }
  }
  function setPromo(code) {
    if (code) localStorage.setItem(PROMO_KEY, JSON.stringify(code));
    else localStorage.removeItem(PROMO_KEY);
  }

  function renderLines() {
    const host = document.querySelector('[data-cart-lines]');
    const empty = document.querySelector('[data-cart-empty]');
    const grid = document.querySelector('[data-cart-grid]');
    if (!host) return;

    const items = window.vaiCart.get();
    if (items.length === 0) {
      if (grid) grid.style.display = 'none';
      if (empty) empty.style.display = 'block';
      return;
    }
    if (grid) grid.style.display = 'grid';
    if (empty) empty.style.display = 'none';

    host.innerHTML = items.map((l, i) => `
      <div class="cart-line" data-line-idx="${i}">
        <div class="cart-line__thumb">
          <div class="cart-line__thumb-ph">
            <!-- TODO: <img src="${esc(l.image)}" alt="${esc(l.name)}"> -->
            ${esc(l.name.split(' ')[0])}
          </div>
        </div>
        <div class="cart-line__main">
          <a class="cart-line__name" href="product-detail.html?id=${encodeURIComponent(l.id)}">${esc(l.name)}</a>
          ${l.size ? `<span class="cart-line__meta">${esc(l.size)}</span>` : ''}
        </div>
        <div class="cart-line__price">${fmt(l.price)}</div>
        <div class="cart-line__qty">
          <button type="button" data-qty="dec" aria-label="Decrease quantity">−</button>
          <input type="number" value="${l.qty}" min="1" max="99" data-qty-input aria-label="Quantity" />
          <button type="button" data-qty="inc" aria-label="Increase quantity">+</button>
        </div>
        <div class="cart-line__total">${fmt(l.price * l.qty)}</div>
        <button type="button" class="cart-line__remove" data-remove aria-label="Remove ${esc(l.name)}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
      </div>
    `).join('');
  }

  function renderSummary() {
    const items = window.vaiCart.get();
    const subtotal = window.vaiCart.subtotal();
    const promo = getPromo();
    let discount = 0;
    if (promo && PROMO_CODES[promo.code]) {
      const p = PROMO_CODES[promo.code];
      discount = p.type === 'pct' ? Math.round(subtotal * p.value / 100) : p.value;
      discount = Math.min(discount, subtotal);
    }
    const afterDiscount = subtotal - discount;
    const shipping = items.length === 0 ? 0 : (afterDiscount >= FREE_SHIPPING_THRESHOLD ? 0 : SHIPPING_FEE);
    const total = afterDiscount + shipping;

    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (el) el.textContent = val;
    };

    set('[data-summary-subtotal]', fmt(subtotal));
    set('[data-summary-discount]', discount > 0 ? '− ' + fmt(discount) : '—');
    set('[data-summary-shipping]', shipping === 0 ? 'Free' : fmt(shipping));
    set('[data-summary-total]', fmt(total));
    set('[data-summary-count]', String(items.reduce((s, l) => s + l.qty, 0)));

    // Persist running totals so checkout can read them
    localStorage.setItem('vai_cart_totals_v1', JSON.stringify({
      subtotal, discount, shipping, total,
      promo: promo ? promo.code : null,
    }));

    // Discount + free-ship row visibility
    const discountRow = document.querySelector('[data-discount-row]');
    if (discountRow) discountRow.style.display = discount > 0 ? 'flex' : 'none';

    // Free-shipping progress bar
    const remaining = FREE_SHIPPING_THRESHOLD - afterDiscount;
    const progress = document.querySelector('[data-free-progress]');
    const progressLabel = document.querySelector('[data-free-progress-label]');
    const progressBar = document.querySelector('[data-free-progress-bar]');
    if (progress) {
      if (items.length === 0 || remaining <= 0) {
        progress.style.display = 'none';
      } else {
        progress.style.display = 'block';
        if (progressLabel) {
          progressLabel.textContent = `Add ${fmt(remaining)} more for free shipping`;
        }
        if (progressBar) {
          const pct = Math.min(100, (afterDiscount / FREE_SHIPPING_THRESHOLD) * 100);
          progressBar.style.width = pct + '%';
        }
      }
    }

    // Applied promo display
    const promoForm = document.querySelector('[data-promo-form]');
    const promoApplied = document.querySelector('[data-promo-applied]');
    if (promo && PROMO_CODES[promo.code]) {
      if (promoForm) promoForm.style.display = 'none';
      if (promoApplied) {
        promoApplied.style.display = 'flex';
        const lbl = promoApplied.querySelector('[data-promo-applied-label]');
        if (lbl) lbl.textContent = `${promo.code} · ${PROMO_CODES[promo.code].label}`;
      }
    } else {
      if (promoForm) promoForm.style.display = 'flex';
      if (promoApplied) promoApplied.style.display = 'none';
    }

    // Checkout button visibility
    const checkoutBtn = document.querySelector('[data-checkout-btn]');
    if (checkoutBtn) checkoutBtn.disabled = items.length === 0;

    // Summary card visibility
    const summary = document.querySelector('.cart-summary');
    if (summary) summary.style.display = items.length === 0 ? 'none' : '';
  }

  function rerender() {
    renderLines();
    renderSummary();
  }

  function wire() {
    document.body.addEventListener('click', (e) => {
      const line = e.target.closest('[data-line-idx]');
      const items = window.vaiCart.get();

      if (line) {
        const idx = parseInt(line.dataset.lineIdx, 10);
        const item = items[idx];
        if (!item) return;

        if (e.target.closest('[data-qty="dec"]')) {
          window.vaiCart.update(item.id, item.size, Math.max(1, item.qty - 1));
          rerender();
          return;
        }
        if (e.target.closest('[data-qty="inc"]')) {
          window.vaiCart.update(item.id, item.size, Math.min(99, item.qty + 1));
          rerender();
          return;
        }
        if (e.target.closest('[data-remove]')) {
          window.vaiCart.remove(item.id, item.size);
          window.vaiToast && window.vaiToast('Removed from cart');
          rerender();
          return;
        }
      }

      // Promo apply
      if (e.target.closest('[data-promo-apply]')) {
        e.preventDefault();
        const input = document.querySelector('[data-promo-input]');
        const code = input.value.trim().toUpperCase();
        if (!code) return;
        if (!PROMO_CODES[code]) {
          window.vaiToast && window.vaiToast('That code is not valid', 'error');
          input.value = '';
          return;
        }
        setPromo({ code });
        window.vaiToast && window.vaiToast(`${code} applied · ${PROMO_CODES[code].label}`);
        input.value = '';
        rerender();
        return;
      }

      // Promo remove
      if (e.target.closest('[data-promo-remove]')) {
        setPromo(null);
        rerender();
        return;
      }
    });

    // Qty input typing
    document.body.addEventListener('change', (e) => {
      if (!e.target.matches('[data-qty-input]')) return;
      const line = e.target.closest('[data-line-idx]');
      if (!line) return;
      const idx = parseInt(line.dataset.lineIdx, 10);
      const items = window.vaiCart.get();
      const item = items[idx];
      if (!item) return;
      let v = parseInt(e.target.value, 10);
      if (!Number.isFinite(v) || v < 1) v = 1;
      v = Math.min(99, v);
      window.vaiCart.update(item.id, item.size, v);
      rerender();
    });

    // Refresh if any other tab modifies cart
    document.addEventListener('cart:changed', rerender);
  }

  function boot() {
    rerender();
    wire();

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.cart__header > *', { stagger: 0.06 });
        scrollReveal('.cart-summary', { y: 20 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
