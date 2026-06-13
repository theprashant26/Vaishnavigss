/* ============================================================
   Vaishnavi Gaushala — Home page script
   ----------------------------------------------------------------
   Responsibilities:
     1. Fetch categories / products / testimonials JSON
     2. Render the asymmetric category grid
     3. Render the bestsellers horizontal scroller
     4. Render testimonials
     5. Wire up scroller arrows
     6. Newsletter form (visual submit, toast)
     7. Kick off home animations after content is in the DOM
   ============================================================ */

(function () {
  'use strict';

  const fmtPrice = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const escape = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → ${r.status}`);
    return r.json();
  }

  // ------------------------------------------------------------
  // 1. Categories — 2 large editorial feature cards
  // ------------------------------------------------------------
  function renderCategories(cats) {
    const host = document.querySelector('[data-cats-grid]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    host.innerHTML = cats.map((cat) => {
      const count = cat.productCount ? `${cat.productCount} products · ` : '';
      return `
        <a class="cat-card cat-card--${escape(cat.id)}"
           href="products.html?cat=${encodeURIComponent(cat.id)}"
           aria-label="Shop ${escape(cat.name)}">
          <div class="cat-card__bg" aria-hidden="true">
            <!-- TODO: replace gradient with <img loading="lazy" src="${escape(cat.image)}" alt=""> -->
          </div>
          <div class="cat-card__body">
            <span class="cat-card__tagline">${count}${escape(cat.tagline)}</span>
            <h3 class="cat-card__name">${escape(cat.name)}</h3>
            <span class="cat-card__cta">Explore</span>
          </div>
        </a>
      `;
    }).join('');
  }

  // ------------------------------------------------------------
  // 2. Bestsellers — horizontal scroller
  // ------------------------------------------------------------
  // Category-name lookup, falls back gracefully if categories missing
  let CAT_INDEX = {};
  function catName(id) {
    return CAT_INDEX[id] || id.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function productCardHTML(p) {
    const hasOld = p.oldPrice && p.oldPrice > p.price;
    const badge = (p.badges || [])[0];
    const badgeMap = {
      bestseller: { cls: 'gold', label: 'Bestseller' },
      sale:       { cls: 'sale', label: 'Sale' },
      new:        { cls: 'new', label: 'New' },
      subscription:{ cls: 'new', label: 'Subscription' },
    };
    const b = badgeMap[badge];

    return `
      <article class="product-card" data-product-id="${escape(p.id)}">
        <div class="product-card__media">
          <div class="product-card__media-placeholder">
            <!-- TODO: <img loading="lazy" src="${escape(p.image)}" alt="${escape(p.imageAlt)}"> -->
            ${escape(p.name)}
          </div>
          ${b ? `<div class="product-card__badges"><span class="badge-vai badge-vai--${b.cls}">${b.label}</span></div>` : ''}
          <button class="product-card__wishlist" aria-label="Add ${escape(p.name)} to wishlist" data-wishlist>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M20 8.5C20 14 12 20 12 20S4 14 4 8.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 8 2.5z"/>
            </svg>
          </button>
        </div>
        <div class="product-card__body">
          <span class="product-card__cat">${escape(catName(p.category))}</span>
          <a class="product-card__name" href="product-detail.html?id=${encodeURIComponent(p.id)}">${escape(p.name)}</a>
          <span class="product-card__weight">${escape(p.weight || '')}</span>
          <div class="product-card__price-row">
            <span class="product-card__price">
              ${fmtPrice(p.price)}${hasOld ? `<span class="product-card__price-old">${fmtPrice(p.oldPrice)}</span>` : ''}
            </span>
            <button class="btn-vaishnavi-primary product-card__add"
                    data-add-to-cart='${JSON.stringify({ id: p.id, name: p.name, price: p.price, size: p.weight, image: p.image })}'>
              Add
            </button>
          </div>
        </div>
      </article>
    `;
  }

  function renderBestsellers(products) {
    const host = document.querySelector('[data-best-scroll]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    // Featured order: bestsellers first, then everything else
    const sorted = products.slice().sort((a, b) =>
      (b.isBestseller ? 1 : 0) - (a.isBestseller ? 1 : 0)
    );
    host.innerHTML = sorted.map(productCardHTML).join('');
  }

  // ------------------------------------------------------------
  // 3. Testimonials
  // ------------------------------------------------------------
  function renderTestimonials(list) {
    const host = document.querySelector('[data-testimonials]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    host.innerHTML = list.slice(0, 3).map(t => {
      const initials = t.name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
      return `
        <article class="testimonial">
          <div class="testimonial__stars" aria-label="${t.rating} out of 5 stars">
            ${'<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.27 5.82 22 7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>'.repeat(Math.round(t.rating))}
          </div>
          <p class="testimonial__quote">"${escape(t.quote)}"</p>
          <div class="testimonial__author">
            <div class="testimonial__avatar" aria-hidden="true">${escape(initials)}</div>
            <div class="testimonial__author-meta">
              <strong>${escape(t.name)}</strong>
              <span>${escape(t.location)} &middot; ${escape(t.product)}</span>
            </div>
          </div>
        </article>
      `;
    }).join('');
  }

  // ------------------------------------------------------------
  // 4. Scroller arrows
  // ------------------------------------------------------------
  function wireScrollerNav() {
    const scroller = document.querySelector('[data-best-scroll]');
    const prev = document.querySelector('[data-scroll-prev]');
    const next = document.querySelector('[data-scroll-next]');
    if (!scroller || !prev || !next) return;

    const nav = prev.closest('.best__nav');

    const step = () => {
      const card = scroller.querySelector('.product-card');
      return card ? card.getBoundingClientRect().width + 16 : 280;
    };
    prev.addEventListener('click', () => scroller.scrollBy({ left: -step(), behavior: 'smooth' }));
    next.addEventListener('click', () => scroller.scrollBy({ left:  step(), behavior: 'smooth' }));

    // Hide the whole nav block when the carousel fits without scrolling.
    // Re-check on resize so the arrows reappear when window shrinks.
    const syncNavVisibility = () => {
      if (!nav) return;
      const overflows = scroller.scrollWidth > scroller.clientWidth + 2;
      nav.style.visibility = overflows ? '' : 'hidden';
    };
    syncNavVisibility();
    window.addEventListener('resize', syncNavVisibility, { passive: true });
  }

  // ------------------------------------------------------------
  // 5. Add-to-cart + wishlist delegation
  // ------------------------------------------------------------
  function wireCartActions() {
    document.body.addEventListener('click', (e) => {
      const addBtn = e.target.closest('[data-add-to-cart]');
      if (addBtn && window.vaiCart) {
        try {
          const payload = JSON.parse(addBtn.getAttribute('data-add-to-cart'));
          window.vaiCart.add(payload, 1);
          window.vaiToast && window.vaiToast(`${payload.name} added to cart`, 'success');
        } catch (err) {
          console.error('add-to-cart payload invalid', err);
        }
        return;
      }
      const wish = e.target.closest('[data-wishlist]');
      if (wish) {
        wish.classList.toggle('is-active');
      }
    });
  }

  // ------------------------------------------------------------
  // 6. Newsletter form
  // ------------------------------------------------------------
  function wireNewsletter() {
    const form = document.querySelector('[data-newsletter]');
    if (!form) return;
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = form.querySelector('input[type="email"]').value.trim();
      if (!email) return;
      // No backend yet — just acknowledge.
      window.vaiToast && window.vaiToast('Thank you. We will write to you with love.', 'success');
      form.reset();
    });
  }

  // ------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------
  // Wire click delegation EAGERLY (not gated on async JSON fetches).
  // Previously this lived inside boot() and only registered after
  // Promise.all resolved — meaning if any of the static JSON fetches
  // were slow/broken, Add-to-cart buttons appeared dead. The handler
  // itself only needs the DOM tree, which is guaranteed once this file
  // has been parsed (it's loaded at end-of-body).
  wireCartActions();
  wireNewsletter();

  async function boot() {
    try {
      const [cats, products, testis] = await Promise.all([
        fetchJSON('/static/data/categories.json'),
        fetchJSON('/static/data/products.json'),
        fetchJSON('/static/data/testimonials.json'),
      ]);

      // Build category-name index for product cards
      CAT_INDEX = cats.reduce((acc, c) => { acc[c.id] = c.name; return acc; }, {});

      renderCategories(cats);
      renderBestsellers(products);
      renderTestimonials(testis);
    } catch (err) {
      console.error('[home] data load failed', err);
    }

    wireScrollerNav();

    // Kick off animations now that content exists
    if (window.vaiAnimations && window.vaiAnimations.initHome) {
      // Defer one frame so DOM is settled
      requestAnimationFrame(() => window.vaiAnimations.initHome());
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
