/* ============================================================
   About page — fetches breed + cow data, renders the breeds
   encyclopedia row and the cow gallery, wires up the photo-gallery
   lightbox, kicks off animations.
   ============================================================ */

(function () {
  'use strict';

  const esc = (s = '') => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));

  // Simple cow silhouette SVG — same outline, tinted via currentColor.
  // Acts as a placeholder until real breed photography is dropped in.
  const COW_SVG = `<svg viewBox="0 0 140 90" fill="currentColor" aria-hidden="true">
    <path d="M18 60c-6 0-9-5-7-10 1-4 4-7 9-9l4-2c2-7 8-12 18-13l24-1c11 0 19 4 24 11l8 3c5 1 8 4 9 8 1 4-2 8-7 9-2 1-4 1-6 0v8c0 3-2 5-5 5h-4c-3 0-5-2-5-5v-4H42v4c0 3-2 5-5 5h-4c-3 0-5-2-5-5v-7c-3 1-7 1-10-1z"/>
    <path d="M105 36l-3-6 4-2 4 6z"/>
    <path d="M28 30c-2 0-4 2-4 4l1 4 3-1 1-3z" opacity="0.7"/>
    <circle cx="98" cy="42" r="1.5" fill="#2B1810"/>
  </svg>`;

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${url} → ${r.status}`);
    return r.json();
  }

  function renderBreeds(breeds) {
    const host = document.querySelector('[data-breeds-grid]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    host.innerHTML = breeds.map(b => `
      <article class="breed-card ${b.isHero ? 'breed-card--hero' : ''}" data-breed="${esc(b.id)}">
        <div class="breed-card__silhouette" aria-hidden="true">
          <!-- TODO: replace silhouette with breed photo when available -->
          ${COW_SVG}
        </div>
        <div class="breed-card__body">
          <span class="breed-card__region">${esc(b.region)}</span>
          <h3 class="breed-card__name">${esc(b.name)}</h3>
          <span class="breed-card__color">${esc(b.color)}</span>
          <p class="breed-card__trait">${esc(b.trait)}</p>
          <p class="breed-card__fact">${esc(b.fact)}</p>
        </div>
      </article>
    `).join('');
  }

  function renderCows(cows) {
    const host = document.querySelector('[data-cows-grid]');
    if (!host) return;
    // [Django migration] Server may have rendered cards already — don't clobber.
    if (host.children.length > 0) return;
    host.innerHTML = cows.map(c => {
      const initial = c.name.charAt(0).toUpperCase();
      const heroCls = c.isHero ? ' cow-card--hero' : '';
      return `
        <article class="cow-card${heroCls}" data-cow-id="${esc(c.id)}">
          <div class="cow-card__media" aria-hidden="true">
            <!-- TODO: replace placeholder with <img src="${esc(c.image)}" alt="${esc(c.imageAlt)}" loading="lazy"> -->
            <div class="cow-card__media-placeholder">${esc(initial)}</div>
          </div>
          <div class="cow-card__body">
            <h3 class="cow-card__name">${esc(c.name)}</h3>
            <div class="cow-card__meta">
              <span><strong>${esc(c.breed)}</strong></span>
              <span>${esc(c.age)}</span>
              <span>Since ${esc(c.joined)}</span>
            </div>
            <p class="cow-card__story">${esc(c.story)}</p>
          </div>
        </article>
      `;
    }).join('');
  }

  function wireLightbox() {
    const modal = document.getElementById('galleryModal');
    if (!modal || !window.bootstrap) return;
    const bsModal = new bootstrap.Modal(modal);
    const target = modal.querySelector('[data-gallery-target]');

    document.querySelectorAll('[data-gallery-open]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const inner = el.querySelector('.gallery__placeholder, img');
        if (!inner || !target) return;
        target.innerHTML = '';
        target.appendChild(inner.cloneNode(true));
        bsModal.show();
      });
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
      });
    });
  }

  async function boot() {
    try {
      const [breeds, cows] = await Promise.all([
        fetchJSON('/static/data/breeds.json'),
        fetchJSON('/static/data/cows.json'),
      ]);
      renderBreeds(breeds);
      renderCows(cows);
    } catch (err) {
      console.error('[about] data load failed', err);
    }

    wireLightbox();

    if (window.vaiAnimations) {
      const { scrollReveal, scrollRevealStagger, countUp } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.about-hero__copy > *', { stagger: 0.08 });
        scrollReveal('.about-hero__portrait', { y: 30 });
        scrollRevealStagger('.timeline__list', '.timeline__item', { stagger: 0.1 });
        scrollRevealStagger('.values__grid', '.value-card', { stagger: 0.08 });
        scrollRevealStagger('.breeds__grid', '.breed-card', { stagger: 0.08 });
        scrollRevealStagger('.cows__grid', '.cow-card', { stagger: 0.08 });
        scrollRevealStagger('.gallery__grid', '.gallery__item', { stagger: 0.04 });
        scrollReveal('.about-cta > *', { stagger: 0.08 });
        countUp('[data-count-up]');
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
