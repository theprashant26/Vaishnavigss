/* ============================================================
   Vaishnavi Gaushala — Shared App Script
   ----------------------------------------------------------------
   Loaded on every page after Bootstrap + GSAP.
   Responsibilities:
     1. Inject reusable HTML partials (navbar, footer, etc.)
     2. Set the active nav link based on the current URL
     3. Stamp the current year into the footer
     4. Sticky-nav scroll state
     5. Cart state in localStorage + cart-count badge
     6. Footer accordion on mobile
     7. Toast helper (window.vaiToast)
     8. Back-to-top button injection + behaviour
     9. Page-fade transition on internal link clicks
     10. Loading splash flag for first-visit
   ============================================================ */

(function () {
  'use strict';

  // ------------------------------------------------------------
  // 0. [Phase 6] One-shot localStorage cart migration to server-side cart.
  // Runs once per browser. If a legacy vai_cart payload exists, POST it to
  // /cart/api/bulk-add/ then clear it. Marker key prevents re-runs.
  // ------------------------------------------------------------
  (function migrateLegacyCart() {
    try {
      if (localStorage.getItem('vai_cart_migrated_v6')) return;
      const raw = localStorage.getItem('vai_cart_v1') || localStorage.getItem('vai_cart');
      if (!raw) {
        localStorage.setItem('vai_cart_migrated_v6', '1');
        return;
      }
      let parsed;
      try { parsed = JSON.parse(raw); } catch { localStorage.setItem('vai_cart_migrated_v6', '1'); return; }

      // Legacy stored either {id: qty} or [{id, name, ...}, ...]. Normalize to {id: qty}.
      let items = {};
      if (Array.isArray(parsed)) {
        for (const entry of parsed) {
          if (entry && entry.id != null) {
            const k = String(entry.id);
            items[k] = (items[k] || 0) + Number(entry.quantity || entry.qty || 1);
          }
        }
      } else if (parsed && typeof parsed === 'object') {
        for (const [k, v] of Object.entries(parsed)) {
          items[String(k)] = Number(v) || 1;
        }
      }
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
      fetch('/cart/api/bulk-add/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ items }),
        credentials: 'same-origin',
      }).finally(() => {
        localStorage.removeItem('vai_cart');
        localStorage.removeItem('vai_cart_v1');
        localStorage.setItem('vai_cart_migrated_v6', '1');
      });
    } catch {
      localStorage.setItem('vai_cart_migrated_v6', '1');
    }
  })();

  // ------------------------------------------------------------
  // 1. Partial loader
  // ------------------------------------------------------------
  /**
   * loadPartial — fetch an HTML fragment and inject it into the
   * first element with [data-partial="<name>"].
   *
   * Usage in markup:
   *   <header data-partial="navbar"></header>
   *   <footer data-partial="footer"></footer>
   *
   * Looks for the file at /components/<name>.html.
   * Resolves once injection + after-callback have run.
   */
  window.loadPartial = async function loadPartial(name, afterInject) {
    const host = document.querySelector(`[data-partial="${name}"]`);
    if (!host) return;
    try {
      const res = await fetch(`components/${name}.html`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`Partial ${name} returned ${res.status}`);
      host.innerHTML = await res.text();
      if (typeof afterInject === 'function') afterInject(host);
      host.dispatchEvent(new CustomEvent('partial:loaded', { bubbles: true, detail: { name } }));
    } catch (err) {
      console.error('[loadPartial]', err);
      // Friendly fallback so the page still functions
      host.innerHTML = `<div style="padding:1rem;color:#7A1F1F;">
        Could not load ${name}. Serve the site via a local server (e.g. VS Code Live Server)
        so fetch() can reach /components/${name}.html.
      </div>`;
    }
  };

  // ------------------------------------------------------------
  // 2. Highlight active nav link
  // ------------------------------------------------------------
  function setActiveNav() {
    // Pull "data-page" from <body>; falls back to filename inference.
    const explicit = document.body.dataset.page;
    let active = explicit;
    if (!active) {
      const path = location.pathname.toLowerCase();
      if (path.includes('product'))   active = 'products';
      else if (path.includes('service')) active = 'services';
      else if (path.includes('about'))   active = 'about';
      else if (path.includes('contact')) active = 'contact';
      else if (path.includes('cart'))    active = 'cart';
      else if (path.includes('login') || path.includes('register')) active = 'login';
      else if (path.includes('profile')) active = 'profile';
      else active = 'home';
    }
    document.querySelectorAll('[data-nav]').forEach(el => {
      if (el.dataset.nav === active) {
        el.setAttribute('aria-current', 'page');
      } else {
        el.removeAttribute('aria-current');
      }
    });
  }

  // ------------------------------------------------------------
  // 3. Year stamp
  // ------------------------------------------------------------
  function stampYear() {
    document.querySelectorAll('[data-year]').forEach(el => {
      el.textContent = String(new Date().getFullYear());
    });
  }

  // ------------------------------------------------------------
  // 4. Sticky nav scroll state
  // ------------------------------------------------------------
  function initStickyNav() {
    const nav = document.querySelector('[data-vai-nav]');
    if (!nav) return;
    const update = () => {
      if (window.scrollY > 8) nav.classList.add('is-scrolled');
      else nav.classList.remove('is-scrolled');
    };
    update();
    window.addEventListener('scroll', update, { passive: true });
  }

  // ------------------------------------------------------------
  // 5. Cart state
  // ------------------------------------------------------------
  const CART_KEY = 'vai_cart_v1';

  const Cart = {
    get() {
      try {
        return JSON.parse(localStorage.getItem(CART_KEY)) || [];
      } catch {
        return [];
      }
    },
    set(items) {
      localStorage.setItem(CART_KEY, JSON.stringify(items));
      this.renderBadge();
      document.dispatchEvent(new CustomEvent('cart:changed', { detail: { items } }));
    },
    count() {
      return this.get().reduce((sum, l) => sum + (l.qty || 0), 0);
    },
    add(product, qty = 1) {
      // [Phase 6] If payload carries a variant_id, route to the server cart.
      // Otherwise fall back to legacy localStorage (only fires on stale
      // pre-migration buttons that the bulk-add migration will eventually clear).
      if (product && product.variant_id) {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
        fetch('/cart/api/add/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
          credentials: 'same-origin',
          body: 'variant_id=' + encodeURIComponent(product.variant_id) + '&quantity=' + qty,
        }).then(r => r.json()).then(data => {
          if (data && data.ok) {
            // Update navbar badge in place; reload for cart page only.
            document.querySelectorAll('[data-cart-count]').forEach(el => {
              el.textContent = data.cart_item_count;
              if (data.cart_item_count > 0) { el.removeAttribute('hidden'); } else { el.setAttribute('hidden', ''); }
            });
            window.vaiToast && window.vaiToast(`${product.name || 'Item'} added to cart`, 'success');
          } else if (data && data.error) {
            window.vaiToast && window.vaiToast(data.error, 'error');
          }
        }).catch(() => {
          window.vaiToast && window.vaiToast('Could not add to cart. Please try again.', 'error');
        });
        return;
      }

      // Legacy localStorage fallback (Phase 1-5)
      const items = this.get();
      const existing = items.find(l => l.id === product.id && l.size === product.size);
      if (existing) {
        existing.qty += qty;
      } else {
        items.push({
          id: product.id,
          name: product.name,
          price: product.price,
          image: product.image,
          size: product.size || product.weight || '',
          qty
        });
      }
      this.set(items);
    },
    update(id, size, qty) {
      const items = this.get().map(l =>
        (l.id === id && l.size === size) ? { ...l, qty } : l
      ).filter(l => l.qty > 0);
      this.set(items);
    },
    remove(id, size) {
      this.set(this.get().filter(l => !(l.id === id && l.size === size)));
    },
    clear() { this.set([]); },
    subtotal() {
      return this.get().reduce((sum, l) => sum + (l.price * l.qty), 0);
    },
    renderBadge() {
      document.querySelectorAll('[data-cart-count]').forEach(el => {
        const c = this.count();
        el.textContent = c;
        el.style.display = c > 0 ? 'inline-flex' : 'none';
      });
    }
  };
  window.vaiCart = Cart;

  // ------------------------------------------------------------
  // 6. Footer accordion (mobile only)
  // ------------------------------------------------------------
  function initFooterAccordion() {
    const cols = document.querySelectorAll('.vai-footer__col-collapsible');
    cols.forEach(col => {
      const h = col.querySelector('h4');
      if (!h) return;
      h.setAttribute('role', 'button');
      h.setAttribute('tabindex', '0');
      const toggle = () => {
        // only operates on mobile widths via CSS, but no harm if user clicks on desktop
        if (window.matchMedia('(max-width: 767.98px)').matches) {
          col.classList.toggle('is-open');
        }
      };
      h.addEventListener('click', toggle);
      h.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
      });
    });
  }

  // ------------------------------------------------------------
  // 7. Toast
  // ------------------------------------------------------------
  function ensureToastNode() {
    let t = document.querySelector('.vai-toast');
    if (!t) {
      t = document.createElement('div');
      t.className = 'vai-toast';
      t.setAttribute('role', 'status');
      t.setAttribute('aria-live', 'polite');
      document.body.appendChild(t);
    }
    return t;
  }
  window.vaiToast = function (message, variant = 'success') {
    const node = ensureToastNode();
    node.className = `vai-toast vai-toast--${variant}`;
    node.textContent = message;
    requestAnimationFrame(() => node.classList.add('is-visible'));
    clearTimeout(node._timer);
    node._timer = setTimeout(() => node.classList.remove('is-visible'), 2400);
  };

  // ------------------------------------------------------------
  // 8. Back-to-top button
  // ------------------------------------------------------------
  function initBackToTop() {
    const btn = document.createElement('button');
    btn.className = 'back-to-top';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Back to top');
    btn.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="18 15 12 9 6 15"/>
      </svg>`;
    document.body.appendChild(btn);

    const onScroll = () => {
      if (window.scrollY > 600) btn.classList.add('is-visible');
      else btn.classList.remove('is-visible');
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    btn.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ------------------------------------------------------------
  // 9. Loading splash (first-visit only, gated by sessionStorage)
  // ------------------------------------------------------------
  const SPLASH_KEY = 'vai_splash_shown_v1';
  function maybeShowSplash() {
    if (sessionStorage.getItem(SPLASH_KEY)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      sessionStorage.setItem(SPLASH_KEY, '1');
      return;
    }
    const splash = document.createElement('div');
    splash.className = 'vai-splash';
    splash.setAttribute('aria-hidden', 'true');
    splash.innerHTML = `
      <img class="vai-splash__mark logo-img logo-img--blend" src="/static/img/vaishnavilogo.jpeg" alt="Vaishnavi Gau Seva Gausansthan" width="96" height="96" />
      <div class="vai-splash__wordmark">Vaishnavi</div>
      <div class="vai-splash__deva">गऊ सेवा</div>
    `;
    document.body.appendChild(splash);
    sessionStorage.setItem(SPLASH_KEY, '1');
    // Fade out after ~1s
    setTimeout(() => {
      splash.classList.add('is-out');
      setTimeout(() => splash.remove(), 500);
    }, 900);
  }

  // ------------------------------------------------------------
  // 10. Page transition (internal link clicks)
  // ------------------------------------------------------------
  function initPageTransitions() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const overlay = document.createElement('div');
    overlay.className = 'page-transition';
    document.body.appendChild(overlay);

    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[href]');
      if (!a) return;
      // Skip if modifier keys, target=_blank, download, external, mailto/tel, hash-only, or data-no-transition
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      if (a.target === '_blank') return;
      if (a.hasAttribute('download')) return;
      if (a.dataset.noTransition !== undefined) return;
      const href = a.getAttribute('href');
      if (!href) return;
      if (/^(mailto:|tel:|javascript:)/i.test(href)) return;
      if (href.startsWith('#')) return;
      try {
        const url = new URL(a.href, location.href);
        if (url.origin !== location.origin) return;
        if (url.pathname === location.pathname && url.search === location.search) return; // same page
      } catch { return; }

      e.preventDefault();
      overlay.classList.add('is-active');
      setTimeout(() => { location.href = a.href; }, 220);
    });

    // pageshow handles back/forward cache returns
    window.addEventListener('pageshow', () => overlay.classList.remove('is-active'));
  }

  // ------------------------------------------------------------
  // 11. Footer newsletter (lives in every footer, on every page)
  // ------------------------------------------------------------
  function initFooterNewsletter() {
    const form = document.querySelector('.vai-footer [data-newsletter]');
    if (!form) return;
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = form.querySelector('input[type="email"]');
      const email = input?.value.trim();
      if (!email) {
        window.vaiToast && window.vaiToast('Please enter your email.', 'error');
        return;
      }
      window.vaiToast && window.vaiToast('Thank you. Letters arriving shortly.', 'success');
      form.reset();
    });
  }

  // ------------------------------------------------------------
  // 12. Bootstrap UI lifecycle
  // ------------------------------------------------------------
  function onReady() {
    maybeShowSplash();
    // [Django migration] The navbar is now rendered server-side via
    // {% include 'partials/_navbar.html' %} in base.html. The previous
    // window.loadPartial('navbar', ...) fetch call has been removed.
    // We invoke its post-inject callback synchronously instead.
    setActiveNav();
    initStickyNav();
    Cart.renderBadge();
    initBackToTop();
    initPageTransitions();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
})();
