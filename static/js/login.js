/* ============================================================
   Login page — tab switch (Email/Phone), OTP digit handling,
   Google placeholder, visual submit (no real auth).
   ============================================================ */

(function () {
  'use strict';

  function wireTabs() {
    // [Django migration] Phase 4: tabs are visual-only on the password login page.
    // They just swap the input placeholder + label between email and phone — the
    // server-side identifier field accepts either. Falls back to the legacy
    // pane-swap behavior on any page that still has multiple .auth-pane elements.
    const input = document.querySelector('[data-identifier-input]');
    const label = document.querySelector('[data-identifier-label]');
    document.querySelectorAll('.auth-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        document.querySelectorAll('.auth-tab').forEach(b => b.classList.toggle('is-active', b === btn));
        if (input) {
          if (target === 'phone') {
            input.placeholder = '+91 9XXXX XXXXX';
            input.type = 'tel';
            input.autocomplete = 'tel';
            if (label) label.textContent = 'Phone';
          } else {
            input.placeholder = 'you@example.com';
            input.type = 'text';
            input.autocomplete = 'username';
            if (label) label.textContent = 'Email';
          }
          input.focus();
        }
        document.querySelectorAll('.auth-pane').forEach(p => p.classList.toggle('is-active', p.dataset.pane === target));
      });
    });
  }

  function wireOtpInputs() {
    const inputs = document.querySelectorAll('[data-otp]');
    inputs.forEach((input, i) => {
      input.addEventListener('input', (e) => {
        // Keep only the last digit
        const v = e.target.value.replace(/\D/g, '');
        e.target.value = v.slice(-1);
        e.target.classList.toggle('is-filled', !!e.target.value);
        if (e.target.value && i < inputs.length - 1) inputs[i + 1].focus();
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && i > 0) {
          inputs[i - 1].focus();
        }
        if (e.key === 'ArrowLeft'  && i > 0) inputs[i - 1].focus();
        if (e.key === 'ArrowRight' && i < inputs.length - 1) inputs[i + 1].focus();
      });
      input.addEventListener('paste', (e) => {
        const txt = (e.clipboardData || window.clipboardData).getData('text');
        const digits = txt.replace(/\D/g, '').slice(0, inputs.length).split('');
        if (digits.length === 0) return;
        e.preventDefault();
        inputs.forEach((el, idx) => {
          el.value = digits[idx] || '';
          el.classList.toggle('is-filled', !!el.value);
        });
        const last = Math.min(digits.length - 1, inputs.length - 1);
        inputs[last].focus();
      });
    });
  }

  function wireForms() {
    document.querySelectorAll('[data-auth-form]').forEach(form => {
      // [Django migration] Phase 4: server-side forms submit normally to Django.
      if (form.hasAttribute('data-server-side')) return;
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const mode = form.dataset.authForm;

        // OTP request (phone tab, step 1)
        if (mode === 'phone-request') {
          const phone = form.elements['phone']?.value.trim();
          if (!phone) {
            window.vaiToast && window.vaiToast('Please enter your phone number.', 'error');
            return;
          }
          // Switch to OTP-verify step
          document.querySelector('[data-pane="phone"] [data-otp-step="1"]')?.classList.add('is-hidden');
          document.querySelector('[data-pane="phone"] [data-otp-step="2"]')?.classList.remove('is-hidden');
          const masked = phone.slice(-4).padStart(phone.length, '•');
          const target = document.querySelector('[data-otp-phone]');
          if (target) target.textContent = masked;
          window.vaiToast && window.vaiToast(`OTP sent to ${phone}`, 'success');
          // Focus first OTP input
          setTimeout(() => document.querySelector('[data-otp]')?.focus(), 80);
          return;
        }

        // OTP verify
        if (mode === 'phone-verify') {
          const code = [...form.querySelectorAll('[data-otp]')].map(i => i.value).join('');
          if (code.length !== 6) {
            window.vaiToast && window.vaiToast('Please enter all 6 digits.', 'error');
            return;
          }
          window.vaiToast && window.vaiToast('Welcome back.', 'success');
          setTimeout(() => location.href = '/profile.html', 600);
          return;
        }

        // Email login
        if (mode === 'email') {
          const email = form.elements['email']?.value.trim();
          const pw = form.elements['password']?.value;
          if (!email || !pw) {
            window.vaiToast && window.vaiToast('Please fill in both fields.', 'error');
            return;
          }
          window.vaiToast && window.vaiToast('Welcome back.', 'success');
          setTimeout(() => location.href = '/profile.html', 600);
          return;
        }
      });
    });
  }

  function wireGoogle() {
    document.querySelectorAll('[data-google]').forEach(btn => {
      btn.addEventListener('click', () => {
        // No real OAuth — just toast and route
        window.vaiToast && window.vaiToast('Continuing with Google…', 'success');
        setTimeout(() => location.href = '/profile.html', 700);
      });
    });
  }

  function wireResend() {
    const btn = document.querySelector('[data-otp-resend]');
    if (!btn) return;
    btn.addEventListener('click', () => {
      btn.disabled = true;
      let n = 30;
      btn.textContent = `Resend in ${n}s`;
      const t = setInterval(() => {
        n -= 1;
        btn.textContent = `Resend in ${n}s`;
        if (n <= 0) {
          clearInterval(t);
          btn.disabled = false;
          btn.textContent = 'Resend OTP';
        }
      }, 1000);
      window.vaiToast && window.vaiToast('OTP resent', 'success');
    });
  }

  function boot() {
    wireTabs();
    wireOtpInputs();
    wireForms();
    wireGoogle();
    wireResend();

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => {
        scrollReveal('.auth-card', { y: 20 });
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
