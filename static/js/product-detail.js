/* ============================================================
   Product detail — fetches a product by ?id=, renders gallery,
   info, tabs and related products. Wires size pills, qty stepper,
   hover-zoom, sticky bottom bar, add-to-cart, share clipboard.
   ============================================================ */

(function () {
  'use strict';

  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // --- State ----------------------------------------------------
  const state = {
    product: null,
    related: [],
    categories: [],
    activeSize: null,
    activePrice: 0,
    qty: 1,
    activeImageIdx: 0,
  };

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → ${r.status}`);
    return r.json();
  }

  // --- Renders --------------------------------------------------
  function renderBreadcrumb() {
    const p = state.product;
    const c = state.categories.find(x => x.id === p.category);
    const host = document.querySelector('[data-breadcrumb]');
    if (!host) return;
    host.innerHTML = `
      <a href="index.html">Home</a>
      <span class="sep">/</span>
      <a href="products.html">Shop</a>
      <span class="sep">/</span>
      <a href="products.html?cat=${encodeURIComponent(p.category)}">${esc(c ? c.name : p.category)}</a>
      <span class="sep">/</span>
      <span aria-current="page">${esc(p.name)}</span>
    `;
  }

  function renderGallery() {
    const main = document.querySelector('[data-pdp-main]');
    const thumbs = document.querySelector('[data-pdp-thumbs]');
    if (!main || !thumbs) return;

    // 4 placeholder "shots" — when real images arrive, swap data and remove modifier classes
    const shots = [1, 2, 3, 4];
    main.classList.add('pdp-gallery__main--zoomable');
    main.innerHTML = `
      <!-- TODO: replace with <img src="${esc(state.product.image)}" alt="${esc(state.product.imageAlt)}"> -->
      <div class="pdp-gallery__placeholder pdp-main--${shots[state.activeImageIdx]}">
        ${esc(state.product.name)}
      </div>
    `;
    thumbs.innerHTML = shots.map((s, i) => `
      <li>
        <button class="pdp-gallery__thumb pdp-gallery__thumb--${s} ${i === state.activeImageIdx ? 'is-active' : ''}"
                type="button"
                data-thumb-idx="${i}"
                aria-label="View image ${i + 1}">
          ${state.product.name.charAt(0)}
        </button>
      </li>
    `).join('');
  }

  function renderRating() {
    const p = state.product;
    const host = document.querySelector('[data-rating]');
    if (!host) return;
    const stars = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.27 5.82 22 7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>';
    host.innerHTML = `
      <span class="pdp-info__rating-stars">${stars.repeat(Math.round(p.rating || 0))}</span>
      <span>${p.rating || 0} (${p.reviewCount || 0} reviews)</span>
    `;
  }

  function renderPrice() {
    const host = document.querySelector('[data-price]');
    if (!host) return;
    const p = state.product;
    const price = state.activePrice || p.price;
    const oldPrice = p.oldPrice;
    const saving = oldPrice && oldPrice > price
      ? Math.round(((oldPrice - price) / oldPrice) * 100)
      : 0;
    host.innerHTML = `
      <strong data-price-current>${fmt(price)}</strong>
      ${oldPrice ? `<span class="pdp-info__price-old">${fmt(oldPrice)}</span>` : ''}
      ${saving ? `<span class="pdp-info__price-save">Save ${saving}%</span>` : ''}
    `;
  }

  function renderSizes() {
    const p = state.product;
    const host = document.querySelector('[data-sizes]');
    const wrap = document.querySelector('[data-sizes-wrap]');
    if (!host || !wrap) return;

    if (!Array.isArray(p.sizes) || p.sizes.length === 0) {
      wrap.style.display = 'none';
      state.activeSize = p.weight || null;
      state.activePrice = p.price;
      return;
    }

    state.activeSize = p.sizes.find(s => s.price === p.price)?.label || p.sizes[0].label;
    state.activePrice = p.sizes.find(s => s.label === state.activeSize)?.price || p.price;

    host.innerHTML = p.sizes.map(s => `
      <li>
        <button class="pdp-size ${s.label === state.activeSize ? 'is-active' : ''}"
                type="button"
                data-size="${esc(s.label)}"
                data-size-price="${s.price}">
          ${esc(s.label)}
          <small>${fmt(s.price)}</small>
        </button>
      </li>
    `).join('');
  }

  function renderHighlights() {
    const host = document.querySelector('[data-highlights]');
    if (!host || !Array.isArray(state.product.highlights)) return;
    host.innerHTML = state.product.highlights.map(h => `<li>${esc(h)}</li>`).join('');
  }

  function renderLongDescription() {
    const host = document.querySelector('[data-long-desc]');
    if (host) host.textContent = state.product.longDescription || state.product.shortDescription || '';
  }

  // Maps JSON nutrition key -> display label
  const NUTRITION_LABELS = {
    energy: 'Energy',
    protein: 'Protein',
    fat: 'Total fat',
    saturatedFat: 'Saturated fat',
    carbs: 'Carbohydrates',
    calcium: 'Calcium',
    cholesterol: 'Cholesterol',
    vitaminA: 'Vitamin A',
    cla: 'Conjugated Linoleic Acid (CLA)',
  };

  function renderNutrition() {
    const lead = document.querySelector('[data-nutrition-lead]');
    const table = document.querySelector('[data-nutrition-table]');
    if (!table) return;
    const data = state.product.nutritionPer100ml || state.product.nutritionPer100g;
    if (!data) {
      if (lead) lead.textContent = 'Nutritional information will be added shortly.';
      table.innerHTML = '';
      return;
    }
    const unit = state.product.nutritionPer100ml ? '100 ml' : '100 g';
    if (lead) lead.textContent = `Approximate values per ${unit} serving, vary seasonally.`;
    table.innerHTML = Object.entries(data).map(([k, v]) => `
      <div class="pdp-nutrition__row" role="row">
        <div role="cell">${esc(NUTRITION_LABELS[k] || k)}</div>
        <div role="cell">${esc(v)}</div>
      </div>
    `).join('');
  }

  function renderHowMade() {
    const host = document.querySelector('[data-howmade]');
    if (host) host.textContent = state.product.howItsMade || '';
  }

  function renderShipping() {
    const host = document.querySelector('[data-shipping]');
    if (host) host.textContent = state.product.shipping || '';
  }

  function renderRelated(allProducts) {
    const host = document.querySelector('[data-related-grid]');
    if (!host) return;
    // Cross-sell: prefer products from the OTHER category for variety,
    // then fall back to same-category if the other category is small.
    const otherCategory = allProducts
      .filter(p => p.id !== state.product.id && p.category !== state.product.category)
      .slice(0, 4);
    const sameCategory = allProducts
      .filter(p => p.id !== state.product.id && p.category === state.product.category)
      .slice(0, Math.max(0, 4 - otherCategory.length));
    const related = otherCategory.concat(sameCategory).slice(0, 4);
    host.innerHTML = related.map(p => `
      <article class="product-card">
        <div class="product-card__media">
          <div class="product-card__media-placeholder">${esc(p.name)}</div>
        </div>
        <div class="product-card__body">
          <span class="product-card__cat">${esc((state.categories.find(c => c.id === p.category) || {}).name || p.category)}</span>
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

  function setHeaderMeta() {
    const p = state.product;
    document.title = `${p.name} — Vaishnavi Gaushala`;
    const desc = document.querySelector('meta[name="description"]');
    if (desc) desc.setAttribute('content', p.shortDescription || p.name);
    const stickyName = document.querySelector('[data-sticky-name]');
    if (stickyName) stickyName.textContent = p.name;
  }

  function renderShort() {
    const host = document.querySelector('[data-short]');
    if (host) host.textContent = state.product.shortDescription || '';
  }

  function renderName() {
    const host = document.querySelector('[data-name]');
    if (host) host.textContent = state.product.name;
    const cat = document.querySelector('[data-cat-label]');
    const c = state.categories.find(x => x.id === state.product.category);
    if (cat) cat.textContent = c ? c.name : state.product.category;
  }

  // --- Hover zoom ----------------------------------------------
  function wireHoverZoom() {
    const main = document.querySelector('[data-pdp-main]');
    if (!main) return;
    main.addEventListener('mousemove', (e) => {
      const r = main.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * 100;
      const y = ((e.clientY - r.top) / r.height) * 100;
      main.style.setProperty('--zoom-x', x + '%');
      main.style.setProperty('--zoom-y', y + '%');
    });
    main.addEventListener('mouseenter', () => main.classList.add('is-zooming'));
    main.addEventListener('mouseleave', () => main.classList.remove('is-zooming'));
  }

  // --- Tabs ----------------------------------------------------
  function wireTabs() {
    const nav = document.querySelector('[data-tabs-nav]');
    if (!nav) return;
    nav.addEventListener('click', (e) => {
      const btn = e.target.closest('.pdp-tab-btn');
      if (!btn) return;
      const id = btn.dataset.tabTarget;
      nav.querySelectorAll('.pdp-tab-btn').forEach(b => b.classList.toggle('is-active', b === btn));
      document.querySelectorAll('.pdp-tab-panel').forEach(panel => {
        panel.classList.toggle('is-active', panel.id === id);
      });
    });
  }

  // --- Sizes / qty / actions ----------------------------------
  function wireBuy() {
    document.body.addEventListener('click', (e) => {
      const size = e.target.closest('[data-size]');
      if (size) {
        state.activeSize = size.dataset.size;
        state.activePrice = parseInt(size.dataset.sizePrice, 10);
        // [Phase 6] Track variant_id so add-to-cart can POST to the server.
        state.activeVariantId = size.dataset.variantId ? parseInt(size.dataset.variantId, 10) : null;
        document.querySelectorAll('[data-size]').forEach(s => s.classList.toggle('is-active', s === size));
        renderPrice();
        const stickyPrice = document.querySelector('[data-sticky-price]');
        if (stickyPrice) stickyPrice.textContent = fmt(state.activePrice);
        return;
      }

      const dec = e.target.closest('[data-qty-dec]');
      const inc = e.target.closest('[data-qty-inc]');
      const input = document.querySelector('[data-qty-input]');
      if (dec && input) {
        state.qty = Math.max(1, state.qty - 1);
        input.value = state.qty;
        return;
      }
      if (inc && input) {
        state.qty = Math.min(99, state.qty + 1);
        input.value = state.qty;
        return;
      }

      const add = e.target.closest('[data-pdp-add]');
      if (add && window.vaiCart) {
        const p = state.product;
        // [Phase 6] If we have a variant_id, route through server cart;
        // vaiCart.add() shows its own toast on success.
        const variantId = state.activeVariantId || null;
        if (variantId) {
          window.vaiCart.add({
            variant_id: variantId, id: p.id, name: p.name,
            price: state.activePrice || p.price,
            image: p.image, size: state.activeSize || p.weight,
          }, state.qty);
        } else {
          window.vaiCart.add({
            id: p.id, name: p.name, price: state.activePrice || p.price,
            image: p.image, size: state.activeSize || p.weight,
          }, state.qty);
          window.vaiToast && window.vaiToast(`${p.name} added to cart`, 'success');
        }
        return;
      }

      const buyNow = e.target.closest('[data-pdp-buynow]');
      if (buyNow && window.vaiCart) {
        const p = state.product;
        const variantId = state.activeVariantId || null;
        if (variantId) {
          // POST then navigate to /cart/ — wait for response so cart is up to date.
          const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
          fetch('/cart/api/add/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
            credentials: 'same-origin',
            body: 'variant_id=' + variantId + '&quantity=' + state.qty,
          }).finally(() => { location.href = '/cart/'; });
        } else {
          window.vaiCart.add({
            id: p.id, name: p.name, price: state.activePrice || p.price,
            image: p.image, size: state.activeSize || p.weight,
          }, state.qty);
          location.href = '/cart/';
        }
        return;
      }

      const thumb = e.target.closest('[data-thumb-idx]');
      if (thumb) {
        state.activeImageIdx = parseInt(thumb.dataset.thumbIdx, 10) || 0;
        renderGallery();
        wireHoverZoom();
        return;
      }

      const wishlist = e.target.closest('[data-wishlist]');
      if (wishlist) {
        wishlist.classList.toggle('is-active');
        const isActive = wishlist.classList.contains('is-active');
        window.vaiToast && window.vaiToast(
          isActive ? 'Added to your wishlist' : 'Removed from wishlist',
          'success'
        );
        return;
      }

      const share = e.target.closest('[data-share]');
      if (share) {
        e.preventDefault();
        if (navigator.share) {
          navigator.share({
            title: state.product.name,
            url: location.href,
          }).catch(() => {});
        } else if (navigator.clipboard) {
          navigator.clipboard.writeText(location.href);
          window.vaiToast && window.vaiToast('Link copied to clipboard', 'success');
        }
        return;
      }

      const addRelated = e.target.closest('[data-add-to-cart]');
      if (addRelated && window.vaiCart) {
        try {
          const payload = JSON.parse(addRelated.getAttribute('data-add-to-cart'));
          window.vaiCart.add(payload, 1);
          window.vaiToast && window.vaiToast(`${payload.name} added to cart`, 'success');
        } catch (err) { console.error(err); }
        return;
      }
    });

    // Qty manual typing
    const input = document.querySelector('[data-qty-input]');
    if (input) {
      input.addEventListener('change', () => {
        const v = parseInt(input.value, 10);
        state.qty = Number.isFinite(v) && v >= 1 ? Math.min(99, v) : 1;
        input.value = state.qty;
      });
    }
  }

  // --- Sticky bar -----------------------------------------------
  function wireSticky() {
    const bar = document.querySelector('[data-sticky]');
    const trigger = document.querySelector('[data-sticky-trigger]');
    if (!bar || !trigger) return;
    const update = () => {
      const r = trigger.getBoundingClientRect();
      const past = r.bottom < 0;
      bar.classList.toggle('is-visible', past);
    };
    window.addEventListener('scroll', update, { passive: true });
    update();
  }

  // --- Boot -----------------------------------------------------
  async function boot() {
    // [Django migration] When the server has rendered the PDP, it stamps
    // window.__VAI_PDP__ with { product, sizes } so we can skip the fetch
    // and the renderXxx() calls — markup is already in the DOM. We just
    // need to wire up interactions (size pills, qty, add-to-cart, tabs).
    if (window.__VAI_PDP__) {
      state.product = window.__VAI_PDP__.product;
      state.activeSize = window.__VAI_PDP__.activeSize || null;
      state.activePrice = window.__VAI_PDP__.activePrice || state.product.price || 0;
      // [Phase 6] Pick the first size pill as initial variant_id so add-to-cart works
      // before the user clicks a size.
      const firstPill = document.querySelector('[data-variant-id]');
      state.activeVariantId = firstPill ? parseInt(firstPill.dataset.variantId, 10) : null;
      wireTabs();
      wireBuy();
      wireHoverZoom();
      wireSticky();
      if (window.vaiAnimations) {
        const { scrollReveal, scrollRevealStagger } = window.vaiAnimations;
        requestAnimationFrame(() => {
          scrollReveal('.pdp-gallery', { y: 30 });
          scrollReveal('.pdp-info > *', { stagger: 0.06 });
          scrollReveal('.pdp-tabs__nav');
          scrollRevealStagger('.pdp-related__grid', '.product-card', { stagger: 0.06 });
        });
      }
      return;
    }

    const params = new URLSearchParams(location.search);
    // Accept either ?id= or ?slug= — id is the documented convention,
    // slug works as an alias for SEO-friendly URLs.
    const id = params.get('id');
    const slug = params.get('slug');

    let products, categories;
    try {
      [products, categories] = await Promise.all([
        fetchJSON('/static/data/products.json'),
        fetchJSON('/static/data/categories.json'),
      ]);
    } catch (err) {
      console.error('[pdp] data load failed', err);
      return;
    }

    const product =
      (id   && products.find(p => p.id   === id)) ||
      (slug && products.find(p => p.slug === slug)) ||
      products[0];
    if (!product) {
      console.error('[pdp] no product found for id/slug', id || slug);
      return;
    }

    state.product = product;
    state.categories = categories;

    setHeaderMeta();
    renderBreadcrumb();
    renderGallery();
    renderName();
    renderRating();
    renderSizes();
    renderPrice();
    renderShort();
    renderHighlights();
    renderLongDescription();
    renderNutrition();
    renderHowMade();
    renderShipping();
    renderRelated(products);

    // Sticky bar copy
    const stickyPrice = document.querySelector('[data-sticky-price]');
    if (stickyPrice) stickyPrice.textContent = fmt(state.activePrice || product.price);

    wireTabs();
    wireBuy();
    wireHoverZoom();
    wireSticky();

    if (window.vaiAnimations) {
      const { scrollReveal, scrollRevealStagger } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.pdp-gallery', { y: 30 });
        scrollReveal('.pdp-info > *', { stagger: 0.06 });
        scrollReveal('.pdp-tabs__nav');
        scrollRevealStagger('.pdp-related__grid', '.product-card', { stagger: 0.06 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
