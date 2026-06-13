/* ============================================================
   Profile page — view switching, mock data render, sub actions,
   address CRUD (visual), settings form save (visual).
   ============================================================ */

(function () {
  'use strict';

  const USER = {
    name: 'Anjali Sharma',
    firstName: 'Anjali',
    email: 'anjali@example.com',
    phone: '+91 98XXX XXXXX',
  };

  // --- Mock data -----------------------------------------------
  const ORDERS = [
    {
      id: 'VAI-N4F2K1',
      date: '12 May 2026',
      total: 2147,
      status: 'delivered',
      statusLabel: 'Delivered',
      items: ['Ghee', 'Khoya', 'Paneer'],
    },
    {
      id: 'VAI-N3R7P9',
      date: '20 May 2026',
      total: 459,
      status: 'ofd',
      statusLabel: 'Out for delivery',
      items: ['Dahi', 'Chaas'],
    },
    {
      id: 'VAI-M2W8L3',
      date: '22 May 2026',
      total: 1799,
      status: 'processing',
      statusLabel: 'Processing',
      items: ['Ghee Box'],
    },
    {
      id: 'VAI-L0X1Q8',
      date: '04 Apr 2026',
      total: 698,
      status: 'cancelled',
      statusLabel: 'Cancelled',
      items: ['Peda', 'Ladoo'],
    },
  ];

  const ADDRESSES = [
    {
      id: 'home',
      tag: 'Home',
      name: 'Anjali Sharma',
      lines: ['B-204 Springfield Apartments', 'Sushant Lok, Gurgaon', 'Haryana — 122002'],
      phone: '+91 98XXX XXXXX',
      isDefault: true,
    },
    {
      id: 'office',
      tag: 'Office',
      name: 'Anjali Sharma',
      lines: ['Acme Co, 12th floor', 'DLF Cyber Hub, Gurgaon', 'Haryana — 122002'],
      phone: '+91 98XXX XXXXX',
    },
  ];

  const WISHLIST_IDS = ['ghee-500', 'peda-250', 'sub-ghee-month'];

  // Local state for sub status (paused/active)
  let subState = 'active';

  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // --- View switching ------------------------------------------
  function setView(name) {
    document.querySelectorAll('.profile-view').forEach(v => {
      v.classList.toggle('is-active', v.dataset.view === name);
    });
    document.querySelectorAll('.profile-nav__list a').forEach(a => {
      a.classList.toggle('is-active', a.dataset.view === name);
    });
    history.replaceState(null, '', '#' + name);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // --- Renders -------------------------------------------------
  function orderRow(o) {
    return `
      <article class="order-card">
        <div class="order-card__head">
          <div>
            <span class="order-card__id">${esc(o.id)}</span>
            <span class="order-card__date">Placed ${esc(o.date)}</span>
          </div>
          <span class="status-pill status-pill--${esc(o.status)}">${esc(o.statusLabel)}</span>
        </div>
        <div class="order-card__items" aria-label="Items">
          ${o.items.map(i => `<div class="order-card__item-thumb">${esc(i)}</div>`).join('')}
        </div>
        <div class="order-card__footer">
          <div class="order-card__total">${fmt(o.total)}</div>
          <div class="order-card__actions">
            ${o.status === 'delivered'
              ? '<button type="button" class="btn-vaishnavi-ghost btn-sm">Buy again</button>'
              : ''}
            <button type="button" class="btn-vaishnavi-ghost btn-sm">View details</button>
          </div>
        </div>
      </article>
    `;
  }

  function renderDashboard() {
    const recent = document.querySelector('[data-dash-recent]');
    if (recent) {
      recent.innerHTML = ORDERS.slice(0, 2).map(orderRow).join('');
    }
    document.querySelectorAll('[data-user-name]').forEach(el => el.textContent = USER.firstName);
  }

  function renderOrders() {
    const host = document.querySelector('[data-orders-list]');
    if (!host) return;
    host.innerHTML = ORDERS.map(orderRow).join('');
  }

  function subActionsHTML() {
    if (subState === 'paused') {
      return `
        <button type="button" class="btn-vaishnavi-primary btn-sm" data-sub-action="resume">Resume</button>
        <button type="button" class="btn-vaishnavi-ghost btn-sm" data-sub-action="cancel">Cancel</button>
      `;
    }
    return `
      <button type="button" class="btn-vaishnavi-ghost btn-sm" data-sub-action="pause">Pause</button>
      <button type="button" class="btn-vaishnavi-ghost btn-sm" data-sub-action="skip">Skip next</button>
      <button type="button" class="btn-vaishnavi-ghost btn-sm" data-sub-action="cancel">Cancel</button>
    `;
  }

  function renderSubs() {
    const host = document.querySelector('[data-subs-list]');
    if (!host) return;
    const isPaused = subState === 'paused';
    host.innerHTML = `
      <article class="sub-card">
        <div class="sub-card__head">
          <div>
            <h3 class="sub-card__name">Daily Milk Subscription</h3>
            <span class="sub-card__cadence">${isPaused ? 'Paused' : '1 L · daily · 6 am–8 am'}</span>
          </div>
          <span class="status-pill ${isPaused ? 'status-pill--cancelled' : 'status-pill--delivered'}">
            ${isPaused ? 'Paused' : 'Active'}
          </span>
        </div>
        <div class="sub-card__meta">
          <div class="sub-card__meta-item">
            <span>Next delivery</span>
            <strong>${isPaused ? '—' : 'Tomorrow, 6:30 am'}</strong>
          </div>
          <div class="sub-card__meta-item">
            <span>Renewal</span>
            <strong>15 Jun 2026</strong>
          </div>
          <div class="sub-card__meta-item">
            <span>Monthly cost</span>
            <strong>₹3,299</strong>
          </div>
          <div class="sub-card__meta-item">
            <span>Started</span>
            <strong>Jan 2026</strong>
          </div>
        </div>
        <div class="sub-card__actions">
          ${subActionsHTML()}
        </div>
      </article>
    `;
  }

  function renderAddresses() {
    const host = document.querySelector('[data-addr-list]');
    if (!host) return;
    host.innerHTML = ADDRESSES.map(a => `
      <article class="addr-card-mine" data-addr="${esc(a.id)}">
        <span class="addr-card-mine__tag">${esc(a.tag)}${a.isDefault ? ' · Default' : ''}</span>
        <span class="addr-card-mine__name">${esc(a.name)}</span>
        <span class="addr-card-mine__lines">
          ${a.lines.map(esc).join('<br/>')}
          <br/>${esc(a.phone)}
        </span>
        <div class="addr-card-mine__actions">
          <button type="button" data-addr-action="edit">Edit</button>
          ${!a.isDefault ? '<button type="button" data-addr-action="default">Set as default</button>' : ''}
          <button type="button" class="danger" data-addr-action="delete">Remove</button>
        </div>
      </article>
    `).join('') + `
      <button type="button" class="addr-add" data-addr-add>
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="5"  x2="12" y2="19"/>
          <line x1="5"  y1="12" x2="19" y2="12"/>
        </svg>
        Add a new address
      </button>
    `;
  }

  async function renderWishlist() {
    const host = document.querySelector('[data-wish-grid]');
    if (!host) return;

    let products = [];
    try {
      const r = await fetch('/static/data/products.json', { cache: 'no-cache' });
      products = await r.json();
    } catch {}

    const items = WISHLIST_IDS
      .map(id => products.find(p => p.id === id))
      .filter(Boolean);

    if (items.length === 0) {
      host.innerHTML = `
        <div class="profile-empty">
          <p>Your wishlist is empty. Save items you like for later.</p>
          <a href="products.html" class="btn-vaishnavi-primary">Browse shop</a>
        </div>
      `;
      return;
    }
    host.innerHTML = items.map(p => `
      <article class="product-card">
        <div class="product-card__media">
          <div class="product-card__media-placeholder">${esc(p.name)}</div>
          <button class="product-card__wishlist is-active" aria-label="Remove ${esc(p.name)} from wishlist">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M20 8.5C20 14 12 20 12 20S4 14 4 8.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 8 2.5z"/>
            </svg>
          </button>
        </div>
        <div class="product-card__body">
          <span class="product-card__cat">${esc(p.category.replace('-', ' & '))}</span>
          <a class="product-card__name" href="product-detail.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a>
          <span class="product-card__weight">${esc(p.weight)}</span>
          <div class="product-card__price-row">
            <span class="product-card__price">${fmt(p.price)}</span>
            <button class="btn-vaishnavi-primary product-card__add"
                    data-add-to-cart='${JSON.stringify({ id: p.id, name: p.name, price: p.price, size: p.weight, image: p.image })}'>
              Add
            </button>
          </div>
        </div>
      </article>
    `).join('');
  }

  function renderSettings() {
    const set = (sel, val) => {
      const el = document.querySelector(sel);
      if (el) el.value = val;
    };
    set('[data-settings-name]', USER.name);
    set('[data-settings-email]', USER.email);
    set('[data-settings-phone]', USER.phone);
  }

  // --- Wire events ---------------------------------------------
  function wire() {
    document.body.addEventListener('click', (e) => {
      const navLink = e.target.closest('.profile-nav__list a[data-view]');
      if (navLink) {
        e.preventDefault();
        setView(navLink.dataset.view);
        return;
      }

      // Subscription actions
      const subAct = e.target.closest('[data-sub-action]');
      if (subAct) {
        const a = subAct.dataset.subAction;
        if (a === 'pause')  { subState = 'paused'; renderSubs(); window.vaiToast && window.vaiToast('Subscription paused'); return; }
        if (a === 'resume') { subState = 'active'; renderSubs(); window.vaiToast && window.vaiToast('Subscription resumed'); return; }
        if (a === 'skip')   { window.vaiToast && window.vaiToast('Next delivery skipped'); return; }
        if (a === 'cancel') {
          if (confirm('Cancel your subscription? You can resume any time.')) {
            window.vaiToast && window.vaiToast('Subscription cancelled');
          }
          return;
        }
      }

      // Address actions
      const addrAct = e.target.closest('[data-addr-action]');
      if (addrAct) {
        const a = addrAct.dataset.addrAction;
        if (a === 'edit')    { window.vaiToast && window.vaiToast('Edit address (UI placeholder)'); return; }
        if (a === 'default') { window.vaiToast && window.vaiToast('Default address updated'); return; }
        if (a === 'delete')  {
          if (confirm('Remove this address?')) {
            const card = addrAct.closest('[data-addr]');
            if (card) card.remove();
            window.vaiToast && window.vaiToast('Address removed');
          }
          return;
        }
      }
      if (e.target.closest('[data-addr-add]')) {
        window.vaiToast && window.vaiToast('Add address (UI placeholder)');
        return;
      }

      // Add-to-cart from wishlist
      const addBtn = e.target.closest('[data-add-to-cart]');
      if (addBtn && window.vaiCart) {
        try {
          const p = JSON.parse(addBtn.getAttribute('data-add-to-cart'));
          window.vaiCart.add(p, 1);
          window.vaiToast && window.vaiToast(`${p.name} added to cart`);
        } catch (err) { console.error(err); }
      }

      // Logout
      if (e.target.closest('[data-logout]')) {
        e.preventDefault();
        window.vaiToast && window.vaiToast('Signed out');
        setTimeout(() => location.href = '/index.html', 600);
      }
    });

    // Settings form submit
    document.querySelectorAll('[data-settings-form]').forEach(form => {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        window.vaiToast && window.vaiToast('Saved', 'success');
      });
    });
  }

  // --- Boot ----------------------------------------------------
  function boot() {
    renderDashboard();
    renderOrders();
    renderSubs();
    renderAddresses();
    renderWishlist();
    renderSettings();
    wire();

    // Initial view from hash or default to dashboard
    const initial = (location.hash || '#dashboard').replace('#', '');
    setView(initial || 'dashboard');

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.profile-nav', { y: 20 });
        scrollReveal('.profile__header', { y: 10 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
