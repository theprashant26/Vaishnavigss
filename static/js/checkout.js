/* ============================================================
   Checkout — 3-step single-page flow.
   Step 1 (Address) → Step 2 (Payment) → Step 3 (Review) → Success.
   Reads the cart from vaiCart, reads totals from cart.js's persistence,
   shows order summary throughout. All payment is visual-only.
   ============================================================ */

(function () {
  'use strict';

  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  const SAVED_ADDRESSES = [
    {
      id: 'home',
      tag: 'Home',
      name: 'Anjali Sharma',
      lines: ['B-204 Springfield Apartments', 'Sushant Lok, Gurgaon', 'Haryana — 122002'],
      phone: '+91 98XXX XXXXX'
    },
    {
      id: 'office',
      tag: 'Office',
      name: 'Anjali Sharma',
      lines: ['Acme Co, 12th floor', 'DLF Cyber Hub, Gurgaon', 'Haryana — 122002'],
      phone: '+91 98XXX XXXXX'
    },
  ];

  const state = {
    currentStep: 1,
    selectedAddressId: SAVED_ADDRESSES[0].id,
    customAddress: null,
    slot: 'sat-am',
    payment: 'upi',
    accepted: false,
  };

  // --- Steps ----------------------------------------------------
  function setStep(n) {
    state.currentStep = n;
    document.querySelectorAll('.steps__item').forEach((el, i) => {
      const num = i + 1;
      el.classList.toggle('is-active', num === n);
      el.classList.toggle('is-done', num < n);
    });
    document.querySelectorAll('.step-panel').forEach(panel => {
      panel.classList.toggle('is-active', parseInt(panel.dataset.step, 10) === n);
    });
    if (n === 3) renderReview();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- Address chips -------------------------------------------
  function renderAddressChips() {
    const host = document.querySelector('[data-addr-chips]');
    if (!host) return;
    host.innerHTML = SAVED_ADDRESSES.map(a => `
      <button type="button" class="addr-chip ${a.id === state.selectedAddressId ? 'is-active' : ''}"
              data-addr-id="${esc(a.id)}">
        <span class="addr-chip__tag">${esc(a.tag)}</span>
        <span class="addr-chip__name">${esc(a.name)}</span>
        <span class="addr-chip__lines">
          ${a.lines.map(l => esc(l)).join('<br/>')}
          <br/>${esc(a.phone)}
        </span>
      </button>
    `).join('') + `
      <button type="button" class="addr-chip addr-chip--new" data-addr-id="new">
        + Use a new address
      </button>
    `;
  }

  // --- Slots ---------------------------------------------------
  function wireSlots() {
    document.querySelectorAll('[data-slot]').forEach(b => {
      b.classList.toggle('is-active', b.dataset.slot === state.slot);
    });
  }

  // --- Order summary right rail -------------------------------
  function renderOrderSummary() {
    const lines = window.vaiCart.get();
    const totalsRaw = localStorage.getItem('vai_cart_totals_v1');
    let totals = null;
    try { totals = JSON.parse(totalsRaw); } catch {}
    if (!totals) {
      const sub = window.vaiCart.subtotal();
      totals = { subtotal: sub, discount: 0, shipping: sub >= 999 ? 0 : 49, total: 0 };
      totals.total = totals.subtotal - totals.discount + totals.shipping;
    }

    const linesHost = document.querySelector('[data-checkout-lines]');
    if (linesHost) {
      linesHost.innerHTML = lines.map(l => `
        <div class="checkout-summary__line">
          <div class="checkout-summary__line-thumb">
            ${esc(l.name.split(' ')[0])}
            <span class="checkout-summary__line-qty">${l.qty}</span>
          </div>
          <div class="checkout-summary__line-main">
            <div class="checkout-summary__line-name">${esc(l.name)}</div>
            ${l.size ? `<div class="checkout-summary__line-meta">${esc(l.size)}</div>` : ''}
          </div>
          <div class="checkout-summary__line-total">${fmt(l.price * l.qty)}</div>
        </div>
      `).join('');
    }
    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (el) el.textContent = val;
    };
    set('[data-co-subtotal]', fmt(totals.subtotal));
    set('[data-co-shipping]', totals.shipping === 0 ? 'Free' : fmt(totals.shipping));
    set('[data-co-total]', fmt(totals.total));

    const discRow = document.querySelector('[data-co-discount-row]');
    if (discRow) {
      discRow.classList.toggle('is-hidden', totals.discount <= 0);
      const v = discRow.querySelector('[data-co-discount]');
      if (v) v.textContent = '− ' + fmt(totals.discount);
    }
  }

  // --- Review step ---------------------------------------------
  function getActiveAddressText() {
    if (state.selectedAddressId === 'new' && state.customAddress) {
      const a = state.customAddress;
      return `<strong>${esc(a.name)}</strong>
              ${esc(a.line1)}${a.line2 ? '<br/>' + esc(a.line2) : ''}
              <br/>${esc(a.city)}, ${esc(a.state)} — ${esc(a.pin)}
              <br/>${esc(a.phone)}`;
    }
    const a = SAVED_ADDRESSES.find(x => x.id === state.selectedAddressId) || SAVED_ADDRESSES[0];
    return `<strong>${esc(a.tag)} · ${esc(a.name)}</strong>
            ${a.lines.map(l => esc(l)).join('<br/>')}
            <br/>${esc(a.phone)}`;
  }

  const SLOT_LABEL = {
    'sat-am':  'Saturday · 8 am – 11 am',
    'sat-pm':  'Saturday · 4 pm – 6 pm',
    'sun-am':  'Sunday · 8 am – 11 am',
    'sun-pm':  'Sunday · 4 pm – 6 pm',
    'daily':   'Daily · 6 am – 8 am',
    'weekday': 'Weekdays · 5 pm – 7 pm',
  };
  const PAY_LABEL = {
    upi:  'UPI · Google Pay, PhonePe, Paytm',
    card: 'Credit / Debit Card',
    nb:   'Net Banking',
    cod:  'Cash on Delivery',
  };

  function renderReview() {
    const set = (sel, html) => {
      const el = document.querySelector(sel);
      if (el) el.innerHTML = html;
    };
    set('[data-review-addr]', getActiveAddressText());
    set('[data-review-slot]', esc(SLOT_LABEL[state.slot] || state.slot));
    set('[data-review-pay]',  esc(PAY_LABEL[state.payment] || state.payment));
  }

  // --- Validation per step -------------------------------------
  function validateStep1() {
    if (state.selectedAddressId === 'new') {
      const form = document.querySelector('[data-new-addr-form]');
      if (!form) return false;
      const required = ['name', 'phone', 'line1', 'city', 'state', 'pin'];
      const data = {};
      for (const f of required) {
        const v = form.elements[f]?.value?.trim();
        if (!v) {
          window.vaiToast && window.vaiToast('Please complete the address fields.', 'error');
          form.elements[f]?.focus();
          return false;
        }
        data[f] = v;
      }
      data.line2 = form.elements['line2']?.value?.trim() || '';
      state.customAddress = data;
    }
    if (!state.slot) {
      window.vaiToast && window.vaiToast('Please pick a delivery slot.', 'error');
      return false;
    }
    return true;
  }

  function validateStep2() {
    if (!state.payment) {
      window.vaiToast && window.vaiToast('Please choose a payment method.', 'error');
      return false;
    }
    return true;
  }

  function validateStep3() {
    if (!state.accepted) {
      window.vaiToast && window.vaiToast('Please accept the terms before placing your order.', 'error');
      return false;
    }
    return true;
  }

  // --- Place order ---------------------------------------------
  function placeOrder() {
    if (!validateStep3()) return;
    const orderId = 'VAI-' + Date.now().toString(36).toUpperCase().slice(-6);
    document.querySelector('[data-order-id]').textContent = orderId;

    // Show success, hide rest
    document.querySelector('[data-checkout-shell]').style.display = 'none';
    document.querySelector('[data-checkout-success]').classList.add('is-visible');

    // Clear cart and promo
    window.vaiCart.clear();
    localStorage.removeItem('vai_promo_v1');
    localStorage.removeItem('vai_cart_totals_v1');
  }

  // --- Wire all events -----------------------------------------
  function wire() {
    document.body.addEventListener('click', (e) => {
      // Step navigation buttons
      const next = e.target.closest('[data-step-next]');
      if (next) {
        if (state.currentStep === 1 && !validateStep1()) return;
        if (state.currentStep === 2 && !validateStep2()) return;
        setStep(state.currentStep + 1);
        return;
      }
      const back = e.target.closest('[data-step-back]');
      if (back) { setStep(Math.max(1, state.currentStep - 1)); return; }
      const editTo = e.target.closest('[data-edit-step]');
      if (editTo) { setStep(parseInt(editTo.dataset.editStep, 10)); return; }

      // Address chips
      const chip = e.target.closest('[data-addr-id]');
      if (chip) {
        state.selectedAddressId = chip.dataset.addrId;
        document.querySelectorAll('[data-addr-id]').forEach(c => c.classList.toggle('is-active', c === chip));
        // Show / hide custom-address form
        const form = document.querySelector('[data-new-addr-wrap]');
        if (form) form.classList.toggle('is-hidden', state.selectedAddressId !== 'new');
        return;
      }

      // Slots
      const slot = e.target.closest('[data-slot]');
      if (slot) {
        state.slot = slot.dataset.slot;
        document.querySelectorAll('[data-slot]').forEach(s => s.classList.toggle('is-active', s === slot));
        return;
      }

      // Place order
      if (e.target.closest('[data-place-order]')) placeOrder();
    });

    // Payment method radios
    document.querySelectorAll('[data-pay-method]').forEach(label => {
      const input = label.querySelector('input');
      label.addEventListener('click', () => {
        if (input) input.checked = true;
        state.payment = label.dataset.payMethod;
        document.querySelectorAll('[data-pay-method]').forEach(l => l.classList.toggle('is-active', l === label));
      });
      if (label.dataset.payMethod === state.payment) label.classList.add('is-active');
    });

    // Terms checkbox
    document.body.addEventListener('change', (e) => {
      if (e.target.matches('[data-terms]')) {
        state.accepted = e.target.checked;
      }
    });
  }

  function boot() {
    // Redirect to cart if empty
    const items = window.vaiCart.get();
    if (items.length === 0) {
      location.replace('/cart.html');
      return;
    }

    renderAddressChips();
    wireSlots();
    renderOrderSummary();
    wire();
    setStep(1);

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.steps', { y: 20 });
        scrollReveal('.checkout-summary', { y: 20 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
