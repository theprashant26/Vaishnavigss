/* ============================================================
   Products page — load JSON, render filter UI + grid, run filter/sort
   client-side, sync state to URL, wire reset + load-more.
   ============================================================ */

(function () {
  'use strict';

  const PAGE_SIZE = 9;
  const fmt = (n) => '₹' + Number(n).toLocaleString('en-IN');
  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // --- State ----------------------------------------------------
  const state = {
    products: [],
    categories: [],
    selectedCats: new Set(),
    priceMin: 0,
    priceMax: 5000,
    activePriceMin: 0,
    activePriceMax: 5000,
    inStockOnly: false,
    sort: 'featured',
    visible: PAGE_SIZE,
  };

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → ${r.status}`);
    return r.json();
  }

  // --- URL <-> state sync ---------------------------------------
  function readURL() {
    const p = new URLSearchParams(location.search);
    const cat = p.get('cat');
    if (cat) state.selectedCats = new Set(cat.split(','));
    const inStock = p.get('inStock');
    if (inStock === '1') state.inStockOnly = true;
    const sort = p.get('sort');
    if (sort) state.sort = sort;
    const pmin = p.get('pmin');
    if (pmin) state.activePriceMin = parseInt(pmin, 10);
    const pmax = p.get('pmax');
    if (pmax) state.activePriceMax = parseInt(pmax, 10);
  }

  function writeURL() {
    const p = new URLSearchParams();
    if (state.selectedCats.size) p.set('cat', [...state.selectedCats].join(','));
    if (state.inStockOnly) p.set('inStock', '1');
    if (state.sort !== 'featured') p.set('sort', state.sort);
    if (state.activePriceMin !== state.priceMin) p.set('pmin', state.activePriceMin);
    if (state.activePriceMax !== state.priceMax) p.set('pmax', state.activePriceMax);
    const qs = p.toString();
    const url = qs ? `${location.pathname}?${qs}` : location.pathname;
    history.replaceState(null, '', url);
  }

  // --- Filter UI ------------------------------------------------
  function renderCategoryFilter() {
    const host = document.querySelector('[data-filter-cats]');
    if (!host) return;
    const counts = state.products.reduce((acc, p) => {
      acc[p.category] = (acc[p.category] || 0) + 1;
      return acc;
    }, {});
    host.innerHTML = state.categories.map(c => `
      <li>
        <label class="filter__check">
          <input type="checkbox" value="${esc(c.id)}" data-cat-cb ${state.selectedCats.has(c.id) ? 'checked' : ''} />
          <span>${esc(c.name)}</span>
          <span class="filter__check-count">${counts[c.id] || 0}</span>
        </label>
      </li>
    `).join('');
  }

  function setupPriceRange() {
    const prices = state.products.map(p => p.price);
    state.priceMin = Math.floor(Math.min(...prices) / 100) * 100;
    state.priceMax = Math.ceil(Math.max(...prices) / 100) * 100;
    if (!Number.isFinite(state.activePriceMin) || state.activePriceMin < state.priceMin) {
      state.activePriceMin = state.priceMin;
    }
    if (!Number.isFinite(state.activePriceMax) || state.activePriceMax > state.priceMax || state.activePriceMax === 5000) {
      state.activePriceMax = state.priceMax;
    }

    const lo = document.querySelector('[data-price-lo]');
    const hi = document.querySelector('[data-price-hi]');
    if (!lo || !hi) return;

    lo.min = state.priceMin; lo.max = state.priceMax; lo.value = state.activePriceMin;
    hi.min = state.priceMin; hi.max = state.priceMax; hi.value = state.activePriceMax;

    const sync = () => {
      let lov = parseInt(lo.value, 10);
      let hiv = parseInt(hi.value, 10);
      if (lov > hiv - 50) lov = hiv - 50;
      if (hiv < lov + 50) hiv = lov + 50;
      lo.value = lov; hi.value = hiv;
      state.activePriceMin = lov;
      state.activePriceMax = hiv;
      updatePriceLabels();
      updateRangeFill();
    };
    lo.addEventListener('input', sync);
    hi.addEventListener('input', sync);
    lo.addEventListener('change', () => { rerender(); writeURL(); });
    hi.addEventListener('change', () => { rerender(); writeURL(); });

    updatePriceLabels();
    updateRangeFill();
  }

  function updatePriceLabels() {
    const loLbl = document.querySelector('[data-price-lo-lbl]');
    const hiLbl = document.querySelector('[data-price-hi-lbl]');
    if (loLbl) loLbl.textContent = fmt(state.activePriceMin);
    if (hiLbl) hiLbl.textContent = fmt(state.activePriceMax);
  }
  function updateRangeFill() {
    const fill = document.querySelector('[data-range-fill]');
    if (!fill) return;
    const span = state.priceMax - state.priceMin;
    if (span <= 0) return;
    const left  = ((state.activePriceMin - state.priceMin) / span) * 100;
    const right = ((state.activePriceMax - state.priceMin) / span) * 100;
    fill.style.left = left + '%';
    fill.style.width = (right - left) + '%';
  }

  // --- Filtering + sorting --------------------------------------
  function applyFilters() {
    let list = state.products.slice();

    if (state.selectedCats.size) {
      list = list.filter(p => state.selectedCats.has(p.category));
    }
    if (state.inStockOnly) {
      list = list.filter(p => p.inStock !== false);
    }
    list = list.filter(p => p.price >= state.activePriceMin && p.price <= state.activePriceMax);

    switch (state.sort) {
      case 'price-asc':  list.sort((a, b) => a.price - b.price); break;
      case 'price-desc': list.sort((a, b) => b.price - a.price); break;
      case 'rating':     list.sort((a, b) => (b.rating || 0) - (a.rating || 0)); break;
      case 'newest':     list.reverse(); break; // shallow: assume input is feed-ordered
      default: /* featured: bestsellers first, then rest */
        list.sort((a, b) => (b.isBestseller ? 1 : 0) - (a.isBestseller ? 1 : 0));
    }
    return list;
  }

  // --- Render ---------------------------------------------------
  function productCard(p) {
    const hasOld = p.oldPrice && p.oldPrice > p.price;
    const badge = (p.badges || [])[0];
    const badgeMap = {
      bestseller: { cls: 'gold', label: 'Bestseller' },
      sale:       { cls: 'sale', label: 'Sale' },
      new:        { cls: 'new',  label: 'New' },
      subscription:{ cls: 'new', label: 'Subscription' },
    };
    const b = badgeMap[badge];
    const cat = state.categories.find(c => c.id === p.category);

    return `
      <article class="product-card" data-product-id="${esc(p.id)}">
        <div class="product-card__media">
          <div class="product-card__media-placeholder">
            <!-- TODO: <img loading="lazy" src="${esc(p.image)}" alt="${esc(p.imageAlt)}"> -->
            ${esc(p.name)}
          </div>
          ${b ? `<div class="product-card__badges"><span class="badge-vai badge-vai--${b.cls}">${b.label}</span></div>` : ''}
          <button class="product-card__wishlist" aria-label="Add ${esc(p.name)} to wishlist" data-wishlist>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M20 8.5C20 14 12 20 12 20S4 14 4 8.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 8 2.5z"/>
            </svg>
          </button>
        </div>
        <div class="product-card__body">
          <span class="product-card__cat">${esc(cat ? cat.name : p.category)}</span>
          <a class="product-card__name" href="product-detail.html?id=${encodeURIComponent(p.id)}">${esc(p.name)}</a>
          <span class="product-card__weight">${esc(p.weight)}</span>
          <div class="product-card__price-row">
            <span class="product-card__price">
              ${fmt(p.price)}${hasOld ? `<span class="product-card__price-old">${fmt(p.oldPrice)}</span>` : ''}
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

  function renderActiveFilterPills() {
    const host = document.querySelector('[data-active-filters]');
    if (!host) return;
    const pills = [];

    state.selectedCats.forEach(id => {
      const c = state.categories.find(x => x.id === id);
      pills.push({ label: c ? c.name : id, type: 'cat', value: id });
    });
    if (state.inStockOnly) {
      pills.push({ label: 'In stock only', type: 'stock' });
    }
    if (state.activePriceMin !== state.priceMin || state.activePriceMax !== state.priceMax) {
      pills.push({ label: `${fmt(state.activePriceMin)} – ${fmt(state.activePriceMax)}`, type: 'price' });
    }
    host.innerHTML = pills.map(p =>
      `<button type="button" class="active-filter-pill" data-pill-type="${esc(p.type)}" data-pill-value="${esc(p.value || '')}">${esc(p.label)}</button>`
    ).join('');
    host.style.display = pills.length ? 'flex' : 'none';
  }

  function renderGrid() {
    const grid = document.querySelector('[data-products-grid]');
    if (!grid) return;

    // [Django migration] If the server has already rendered cards, DO NOT
    // overwrite them. The JS-rendered cards come from /static/data/products.json
    // which is frozen at Phase 1 — it has no variant_id, so the Add buttons on
    // those JS cards fall through the legacy localStorage path and never POST
    // to /cart/api/add/. The server-rendered cards (from partials/_product_card.html)
    // carry the real variant_id and work correctly.
    //
    // Client-side filtering still updates the URL via writeURL(); applying
    // filters reloads the page (form submit) and Django renders with the new
    // query params. The Apply Filters button in the sidebar is the trigger.
    if (grid.children.length > 0 && grid.querySelector('[data-product-id]')) {
      return;
    }

    const list = applyFilters();
    const empty = document.querySelector('[data-products-empty]');
    const count = document.querySelector('[data-products-count]');
    const more  = document.querySelector('[data-loadmore]');

    if (list.length === 0) {
      grid.innerHTML = '';
      if (empty) empty.style.display = 'block';
      if (count) count.textContent = '0';
      if (more)  more.style.display = 'none';
      return;
    }
    if (empty) empty.style.display = 'none';

    const slice = list.slice(0, state.visible);
    grid.innerHTML = slice.map(productCard).join('');
    if (count) count.textContent = String(list.length);

    if (more) more.style.display = list.length > state.visible ? 'block' : 'none';
  }

  function rerender() {
    renderActiveFilterPills();
    renderGrid();
  }

  // --- Wire events ----------------------------------------------
  function wireEvents() {
    document.body.addEventListener('change', (e) => {
      // Category checkboxes
      if (e.target.matches('[data-cat-cb]')) {
        const id = e.target.value;
        if (e.target.checked) state.selectedCats.add(id);
        else state.selectedCats.delete(id);
        state.visible = PAGE_SIZE;
        rerender(); writeURL();
        return;
      }
      // In-stock switch
      if (e.target.matches('[data-instock]')) {
        state.inStockOnly = e.target.checked;
        state.visible = PAGE_SIZE;
        rerender(); writeURL();
        return;
      }
      // Sort
      if (e.target.matches('[data-sort]')) {
        state.sort = e.target.value;
        state.visible = PAGE_SIZE;
        rerender(); writeURL();
        return;
      }
    });

    document.body.addEventListener('click', (e) => {
      // Reset filters
      if (e.target.closest('[data-reset]')) {
        state.selectedCats.clear();
        state.inStockOnly = false;
        state.sort = 'featured';
        state.activePriceMin = state.priceMin;
        state.activePriceMax = state.priceMax;
        state.visible = PAGE_SIZE;
        // Reset form controls
        document.querySelectorAll('[data-cat-cb]').forEach(cb => { cb.checked = false; });
        const sw = document.querySelector('[data-instock]'); if (sw) sw.checked = false;
        const sel = document.querySelector('[data-sort]'); if (sel) sel.value = 'featured';
        const lo = document.querySelector('[data-price-lo]'); if (lo) lo.value = state.priceMin;
        const hi = document.querySelector('[data-price-hi]'); if (hi) hi.value = state.priceMax;
        updatePriceLabels(); updateRangeFill();
        rerender(); writeURL();
        return;
      }
      // Load more
      if (e.target.closest('[data-loadmore]')) {
        state.visible += PAGE_SIZE;
        rerender();
        return;
      }
      // Active filter pill
      const pill = e.target.closest('[data-pill-type]');
      if (pill) {
        const type = pill.dataset.pillType;
        const value = pill.dataset.pillValue;
        if (type === 'cat')  {
          state.selectedCats.delete(value);
          const cb = document.querySelector(`[data-cat-cb][value="${value}"]`);
          if (cb) cb.checked = false;
        }
        if (type === 'stock') {
          state.inStockOnly = false;
          const sw = document.querySelector('[data-instock]'); if (sw) sw.checked = false;
        }
        if (type === 'price') {
          state.activePriceMin = state.priceMin;
          state.activePriceMax = state.priceMax;
          const lo = document.querySelector('[data-price-lo]'); if (lo) lo.value = state.priceMin;
          const hi = document.querySelector('[data-price-hi]'); if (hi) hi.value = state.priceMax;
          updatePriceLabels(); updateRangeFill();
        }
        rerender(); writeURL();
        return;
      }
      // Add-to-cart
      const addBtn = e.target.closest('[data-add-to-cart]');
      if (addBtn && window.vaiCart) {
        try {
          const payload = JSON.parse(addBtn.getAttribute('data-add-to-cart'));
          window.vaiCart.add(payload, 1);
          window.vaiToast && window.vaiToast(`${payload.name} added to cart`, 'success');
        } catch (err) { console.error(err); }
        return;
      }
      // Wishlist heart
      const wish = e.target.closest('[data-wishlist]');
      if (wish) wish.classList.toggle('is-active');
    });
  }

  // Wire click/change delegation EAGERLY — independent of the async
  // JSON fetch path below. Previously this was inside boot(), so if the
  // /static/data fetches errored, the catch() returned early and Add
  // buttons + filter UI all stopped responding.
  wireEvents();

  // --- Boot -----------------------------------------------------
  async function boot() {
    readURL();
    try {
      const [products, categories] = await Promise.all([
        fetchJSON('/static/data/products.json'),
        fetchJSON('/static/data/categories.json'),
      ]);
      state.products = products;
      state.categories = categories;
    } catch (err) {
      console.error('[products] data load failed', err);
      return;
    }

    // Set initial sort UI value
    const sortSel = document.querySelector('[data-sort]');
    if (sortSel) sortSel.value = state.sort;
    // Set initial in-stock toggle
    const sw = document.querySelector('[data-instock]');
    if (sw) sw.checked = state.inStockOnly;

    renderCategoryFilter();
    setupPriceRange();
    // wireEvents() is now called eagerly at module load — see above.
    rerender();

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.products-hero > div > *', { stagger: 0.06 });
        scrollReveal('.filter-sidebar', { y: 20 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
