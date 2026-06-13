/* ============================================================
   Services page — renders:
     1. Non-subscription services from services.json (4 cards)
     2. 3-tier subscription plans from subscriptions.json (tabbed)
   Wires tab switching + animations.
   ============================================================ */

(function () {
  'use strict';

  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // Icon SVGs for the 4 non-subscription service cards
  const ICONS = {
    visit: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 1 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
    adopt: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78z"/></svg>`,
    wholesale: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="12" rx="1"/><path d="M3 12h18"/><path d="M8 8V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v3"/></svg>`,
    pooja: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v3"/><path d="M8 5l2 4h4l2-4"/><path d="M6 9c-2 0-3 1-3 3 0 4 4 9 9 9s9-5 9-9c0-2-1-3-3-3"/></svg>`,
  };

  // The 4 non-subscription services
  const NON_SUB_SERVICES = [
    {
      id: 'visit',
      icon: 'visit',
      name: 'Gaushala Visits',
      tagline: 'Meet the cows, see the bilona.',
      description: 'Free guided visits every weekend, 9 AM – 12 PM. Walk the sheds, watch the bilona churn, feed our cows by hand, stay for prasad if you wish. Children very welcome.',
      price: 'Free',
      unit: 'Saturdays &amp; Sundays · pre-book',
      cta: 'Book a Visit',
      ctaHref: '/contact.html?topic=visit'
    },
    {
      id: 'adoption',
      icon: 'adopt',
      name: 'Cow Adoption &amp; Sponsorship',
      tagline: 'Sponsor a cow\'s care. Get her stories.',
      description: 'Adopt one cow by name. Sponsor her fodder, vet care and shelter for ₹3,000 / month — or ₹35,000 for a full year. Receive a certificate, monthly photos, and a quarterly invitation to visit her at the gaushala.',
      price: '₹3,000',
      unit: 'per month · cow of your choice',
      cta: 'Adopt a Cow',
      ctaHref: '/contact.html?topic=adoption'
    },
    {
      id: 'wholesale',
      icon: 'wholesale',
      name: 'Wholesale &amp; Bulk Orders',
      tagline: 'For restaurants, temples, weddings.',
      description: 'Reliable bulk supply of A2 milk, ghee, paneer and traditional snacks — with traceability, lab reports, and dedicated dispatch routing. Minimum order ₹10,000.',
      price: 'Custom',
      unit: 'volume pricing · ₹10,000 min',
      cta: 'Request a Quote',
      ctaHref: '/contact.html?topic=wholesale'
    },
    {
      id: 'pooja',
      icon: 'pooja',
      name: 'Custom Pooja &amp; Wedding Hampers',
      tagline: 'Bespoke ghee + sweet hampers.',
      description: 'Customised hampers for Diwali, Janmashtami, weddings, grihapravesh and corporate gifting. Brass diyas, ghee in glass, snacks in cloth-wrapped boxes. We can brand the box with your name or family crest.',
      price: 'From ₹999',
      unit: 'per hamper · branded boxes available',
      cta: 'Build a Hamper',
      ctaHref: '/contact.html?topic=hamper'
    },
  ];

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → ${r.status}`);
    return r.json();
  }

  // --- Non-subscription services ---------------------------------
  function renderNonSubServices() {
    const host = document.querySelector('[data-svc-grid]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    host.innerHTML = NON_SUB_SERVICES.map(s => `
      <article class="svc-card" id="${esc(s.id)}">
        <div class="svc-card__icon" aria-hidden="true">${ICONS[s.icon] || ICONS.visit}</div>
        <h3 class="svc-card__title">${s.name}</h3>
        <p class="svc-card__tagline">${s.tagline}</p>
        <p class="svc-card__desc">${s.description}</p>
        <div class="svc-card__price">${s.price}<small>${s.unit}</small></div>
        <a class="btn-vaishnavi-primary btn-sm svc-card__cta" href="${esc(s.ctaHref)}">${s.cta}</a>
      </article>
    `).join('');
  }

  // --- Subscription plans ----------------------------------------
  function planCardHTML(plan) {
    const cls = plan.badge === 'Most Popular' ? 'plan-card--popular'
              : plan.badge === 'Best Value'   ? 'plan-card--best'
              : '';
    const hasSaving = typeof plan.saving === 'number' && plan.saving > 0;
    const period = plan.period === 'one-time' ? 'one-time' : `/ ${plan.period}`;
    const check = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>`;
    return `
      <article class="plan-card ${cls}">
        ${plan.badge ? `<span class="plan-card__badge">${esc(plan.badge)}</span>` : ''}
        <h4 class="plan-card__name">${esc(plan.name)}</h4>
        <p class="plan-card__contents">${esc(plan.contents)}</p>
        <div class="plan-card__price">
          <strong>${fmt(plan.price)}</strong>
          <span class="plan-card__price-period">${esc(period)}</span>
        </div>
        ${hasSaving ? `
          <span class="plan-card__saving">
            Save ${fmt(plan.saving)}
            <span class="plan-card__alacarte">${fmt(plan.alacarte)}</span>
          </span>` : ''}
        <ul class="plan-card__items" role="list">
          ${plan.items.map(i => `<li>${check}<span>${esc(i)}</span></li>`).join('')}
        </ul>
        <a class="btn-vaishnavi-primary btn-sm plan-card__cta" href="register.html?plan=${esc(plan.id)}">Subscribe</a>
      </article>
    `;
  }

  function renderSubscriptions(data) {
    const tabsHost = document.querySelector('[data-subs-tabs]');
    const panesHost = document.querySelector('[data-subs-panes]');
    if (!tabsHost || !panesHost) return;
    // [Django migration] Server may have rendered tabs/panes already — don't clobber.
    if (tabsHost.children.length > 0 || panesHost.children.length > 0) return;

    tabsHost.innerHTML = data.tiers.map((t, i) => `
      <button type="button"
              class="subs__tab ${i === 0 ? 'is-active' : ''}"
              data-subs-tab="${esc(t.id)}"
              role="tab">${esc(t.name)}</button>
    `).join('');

    panesHost.innerHTML = data.tiers.map((t, i) => `
      <div class="subs__pane ${i === 0 ? 'is-active' : ''}" data-subs-pane="${esc(t.id)}" role="tabpanel">
        <p class="subs__pane-tagline">${esc(t.tagline)}</p>
        <div class="subs__plan-grid">
          ${t.plans.map(planCardHTML).join('')}
        </div>
        ${t.footnote ? `<p class="subs__footnote">${esc(t.footnote)}</p>` : ''}
      </div>
    `).join('');
  }

  function wireSubsTabs() {
    document.body.addEventListener('click', (e) => {
      const tab = e.target.closest('[data-subs-tab]');
      if (!tab) return;
      const id = tab.dataset.subsTab;
      document.querySelectorAll('[data-subs-tab]').forEach(t =>
        t.classList.toggle('is-active', t === tab)
      );
      document.querySelectorAll('[data-subs-pane]').forEach(p =>
        p.classList.toggle('is-active', p.dataset.subsPane === id)
      );
    });
  }

  async function boot() {
    renderNonSubServices();
    try {
      const data = await fetchJSON('/static/data/subscriptions.json');
      renderSubscriptions(data);
    } catch (err) {
      console.error('[services] subscriptions load failed', err);
    }
    wireSubsTabs();

    if (window.vaiAnimations) {
      const { scrollReveal, scrollRevealStagger } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.svc-hero > div > *', { stagger: 0.08 });
        scrollReveal('.subs__tabs', { y: 20 });
        scrollRevealStagger('.subs__pane.is-active .subs__plan-grid', '.plan-card', { stagger: 0.06 });
        scrollRevealStagger('.svc-grid', '.svc-card', { stagger: 0.08 });
        scrollRevealStagger('.how__steps', '.how__step', { stagger: 0.12 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
