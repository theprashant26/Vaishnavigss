/* ============================================================
   Vaishnavi Gaushala — GSAP Animation Module
   ----------------------------------------------------------------
   One file, page-specific init functions exported on window.
   Every timeline:
     - duration 0.6–1.0s
     - ease "power2.out" (or ease-out cubic)
     - bails immediately under prefers-reduced-motion
   ============================================================ */

(function () {
  'use strict';

  const motionReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Register ScrollTrigger if available
  if (window.gsap && window.ScrollTrigger) {
    gsap.registerPlugin(ScrollTrigger);
  }

  // ------------------------------------------------------------
  // Shared utilities
  // ------------------------------------------------------------

  /**
   * Reveal a list of elements with a stagger on scroll.
   * Adds `.reveal` class manually in markup OR pass selectors.
   */
  function scrollReveal(selector, options = {}) {
    if (motionReduced || !window.gsap || !window.ScrollTrigger) return;
    const els = typeof selector === 'string'
      ? gsap.utils.toArray(selector)
      : selector;
    if (!els.length) return;

    gsap.set(els, { opacity: 0, y: options.y ?? 40 });

    els.forEach((el) => {
      gsap.to(el, {
        opacity: 1,
        y: 0,
        duration: options.duration ?? 0.8,
        ease: options.ease ?? 'power2.out',
        scrollTrigger: {
          trigger: el,
          start: options.start ?? 'top 85%',
          once: true,
        },
        delay: options.delay ?? 0,
      });
    });
  }

  /**
   * Stagger reveal within a single container (e.g. cards in a grid).
   */
  function scrollRevealStagger(containerSelector, childSelector, options = {}) {
    if (motionReduced || !window.gsap || !window.ScrollTrigger) return;
    const containers = gsap.utils.toArray(containerSelector);
    containers.forEach((container) => {
      const children = container.querySelectorAll(childSelector);
      if (!children.length) return;
      gsap.set(children, { opacity: 0, y: options.y ?? 40 });
      gsap.to(children, {
        opacity: 1,
        y: 0,
        duration: options.duration ?? 0.8,
        ease: 'power2.out',
        stagger: options.stagger ?? 0.08,
        scrollTrigger: {
          trigger: container,
          start: 'top 80%',
          once: true,
        },
      });
    });
  }

  /**
   * Count-up animation: target element's textContent must start as
   * a number (or "35+" — we'll animate the numeric portion).
   */
  function countUp(selector, options = {}) {
    if (motionReduced || !window.gsap || !window.ScrollTrigger) return;
    const els = gsap.utils.toArray(selector);
    els.forEach((el) => {
      const raw = el.textContent.trim();
      const match = raw.match(/(\d+)(.*)/);
      if (!match) return;
      const endNum = parseInt(match[1], 10);
      const suffix = match[2] || '';
      const obj = { val: 0 };
      gsap.to(obj, {
        val: endNum,
        duration: options.duration ?? 1.4,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: el,
          start: 'top 90%',
          once: true,
        },
        onUpdate() {
          el.textContent = Math.round(obj.val) + suffix;
        },
      });
    });
  }

  // ------------------------------------------------------------
  // Home page
  // ------------------------------------------------------------
  function initHomeAnimations() {
    if (motionReduced || !window.gsap) return;

    // --- Hero entry timeline ---
    const heroTl = gsap.timeline({ defaults: { ease: 'power2.out' } });

    const heroWords = gsap.utils.toArray('.hero__title .word');
    const heroDeva = document.querySelector('.hero__deva');
    const heroLead = document.querySelector('.hero__lead');
    const heroCtas = document.querySelector('.hero__ctas');
    const heroMeta = document.querySelector('.hero__meta');
    const heroVisual = document.querySelector('.hero__visual');
    const heroLotus = document.querySelector('.hero__visual-lotus');
    const heroMark = document.querySelector('.hero__visual-mark');
    const heroBadge = document.querySelector('.hero__visual-badge');

    if (heroWords.length) {
      gsap.set(heroWords, { opacity: 0, y: 28 });
      heroTl.to(heroWords, { opacity: 1, y: 0, duration: 0.7, stagger: 0.08 }, 0);
    }
    if (heroDeva) {
      gsap.set(heroDeva, { opacity: 0, y: 16 });
      heroTl.to(heroDeva, { opacity: 1, y: 0, duration: 0.7 }, '-=0.35');
    }
    if (heroLead) {
      gsap.set(heroLead, { opacity: 0, y: 16 });
      heroTl.to(heroLead, { opacity: 1, y: 0, duration: 0.7 }, '-=0.45');
    }
    if (heroCtas) {
      gsap.set(heroCtas, { opacity: 0, y: 14 });
      heroTl.to(heroCtas, { opacity: 1, y: 0, duration: 0.6 }, '-=0.45');
    }
    if (heroMeta) {
      gsap.set(heroMeta, { opacity: 0, y: 14 });
      heroTl.to(heroMeta, { opacity: 1, y: 0, duration: 0.6 }, '-=0.35');
    }
    if (heroVisual) {
      gsap.set(heroVisual, { opacity: 0, scale: 0.92 });
      heroTl.to(heroVisual, { opacity: 1, scale: 1, duration: 0.9 }, 0.15);
    }
    if (heroLotus) {
      gsap.set(heroLotus, { opacity: 0, y: -10 });
      heroTl.to(heroLotus, { opacity: 0.9, y: 0, duration: 0.7 }, '-=0.5');
    }
    if (heroMark) {
      gsap.set(heroMark, { opacity: 0, scale: 0.6 });
      heroTl.to(heroMark, { opacity: 1, scale: 1, duration: 0.6 }, '-=0.4');
    }
    if (heroBadge) {
      gsap.set(heroBadge, { opacity: 0, x: 30 });
      heroTl.to(heroBadge, { opacity: 1, x: 0, duration: 0.6 }, '-=0.55');
    }

    // --- ScrollTrigger reveals per section ---
    scrollRevealStagger('.trust__grid', '.trust__item', { stagger: 0.07, y: 20 });
    scrollReveal('.cats .section-heading');
    scrollRevealStagger('.cats__grid', '.cat-card', { stagger: 0.08 });
    scrollReveal('.story__media', { y: 60 });
    scrollReveal('.story__copy > *', { stagger: 0.06 });
    scrollReveal('.best__header');
    scrollRevealStagger('.best__scroll', '.product-card', { stagger: 0.06 });
    scrollReveal('.sub-teaser__inner > *', { stagger: 0.08 });
    scrollReveal('.testimonials .section-heading');
    scrollRevealStagger('.testimonials__grid', '.testimonial', { stagger: 0.1 });
    scrollReveal('.blog .section-heading');
    scrollRevealStagger('.blog__grid', '.blog-card', { stagger: 0.1 });
    scrollRevealStagger('.contact-strip__grid', '.contact-card', { stagger: 0.1 });

    // --- Count-up for hero meta numbers ---
    countUp('[data-count-up]');
  }

  // Expose
  window.vaiAnimations = {
    initHome: initHomeAnimations,
    scrollReveal,
    scrollRevealStagger,
    countUp,
  };
})();
