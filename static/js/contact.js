/* ============================================================
   Contact page — form submit handler (visual only), prefill from
   ?topic= query param, FAQ accessibility, animations.
   ============================================================ */

(function () {
  'use strict';

  function prefillTopic() {
    const params = new URLSearchParams(location.search);
    const topic = params.get('topic');
    if (!topic) return;
    const select = document.querySelector('[name="subject"]');
    if (!select) return;
    // Match by value (case-insensitive)
    const opt = Array.from(select.options).find(
      o => o.value.toLowerCase() === topic.toLowerCase()
    );
    if (opt) select.value = opt.value;
  }

  function wireForm() {
    const form = document.querySelector('[data-contact-form]');
    if (!form) return;
    form.addEventListener('submit', (e) => {
      e.preventDefault();

      // Minimal client-side validation
      const name  = form.elements['name'].value.trim();
      const email = form.elements['email'].value.trim();
      const msg   = form.elements['message'].value.trim();
      if (!name || !email || !msg) {
        window.vaiToast && window.vaiToast('Please fill name, email and message.', 'error');
        return;
      }

      // No backend yet — visual acknowledgement only.
      window.vaiToast && window.vaiToast('Message received. We will reply within a day.', 'success');
      form.reset();
    });
  }

  function boot() {
    prefillTopic();
    wireForm();

    if (window.vaiAnimations) {
      const { scrollReveal, scrollRevealStagger } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.contact-hero > div > *', { stagger: 0.06 });
        scrollReveal('.contact-form-card', { y: 30 });
        scrollReveal('.contact-info-card', { y: 30 });
        scrollRevealStagger('.faq__list', '.faq__item', { stagger: 0.06 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
