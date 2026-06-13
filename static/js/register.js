/* ============================================================
   Register page — 2-step flow:
     Step 1: details form (name, phone, email, password, confirm)
     Step 2: OTP verify (accepts any 6 digits)
   Plus Google placeholder. No real auth backend.
   ============================================================ */

(function () {
  'use strict';

  const state = {
    step: 1,
    phone: '',
  };

  // --- Password strength ---------------------------------------
  function scorePw(pw) {
    let s = 0;
    if (pw.length >= 8) s += 1;
    if (/[A-Z]/.test(pw)) s += 1;
    if (/[0-9]/.test(pw)) s += 1;
    if (/[^A-Za-z0-9]/.test(pw)) s += 1;
    return s;
  }
  function wirePw() {
    const input = document.querySelector('[data-pw]');
    const meter = document.querySelector('[data-pw-meter]');
    const label = document.querySelector('[data-pw-label]');
    if (!input || !meter) return;
    input.addEventListener('input', () => {
      const s = scorePw(input.value);
      const map = ['', 'is-weak', 'is-fair', 'is-good', 'is-strong'];
      const labelMap = ['', 'Weak', 'Fair', 'Good', 'Strong'];
      meter.className = 'pw-strength ' + (map[s] || '');
      if (label) label.textContent = input.value ? labelMap[s] : '';
    });
  }

  // --- OTP -----------------------------------------------------
  // [Django migration] Phase 4: concat the 6 visible inputs into a hidden
  // [name="code"] field so the server receives one value on submit.
  function syncOtpHidden() {
    const hidden = document.querySelector('[data-otp-collect]');
    if (!hidden) return;
    const inputs = document.querySelectorAll('[data-otp]');
    hidden.value = Array.from(inputs).map(i => i.value).join('');
  }
  function wireOtpInputs() {
    const inputs = document.querySelectorAll('[data-otp]');
    inputs.forEach((input, i) => {
      input.addEventListener('input', (e) => {
        const v = e.target.value.replace(/\D/g, '');
        e.target.value = v.slice(-1);
        e.target.classList.toggle('is-filled', !!e.target.value);
        if (e.target.value && i < inputs.length - 1) inputs[i + 1].focus();
        syncOtpHidden();
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && i > 0) inputs[i - 1].focus();
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
        inputs[Math.min(digits.length - 1, inputs.length - 1)].focus();
        syncOtpHidden();
      });
    });
    // Belt-and-braces sync on submit, in case typing finished without leaving last field.
    const otpForm = document.querySelector('[data-otp-collect]')?.closest('form');
    if (otpForm) otpForm.addEventListener('submit', syncOtpHidden);
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

  // --- Steps ---------------------------------------------------
  function setStep(n) {
    state.step = n;
    document.querySelectorAll('.auth-step').forEach(el => {
      el.classList.toggle('is-active', parseInt(el.dataset.regStep, 10) === n);
    });
    if (n === 2) {
      setTimeout(() => document.querySelector('[data-otp]')?.focus(), 80);
    }
  }

  // --- Form submission -----------------------------------------
  function wireForms() {
    const detailsForm = document.querySelector('[data-reg-details]');
    // [Django migration] Phase 4: when the form has data-server-side, let it
    // submit naturally to Django. Otherwise keep the legacy visual-only flow.
    if (detailsForm && !detailsForm.hasAttribute('data-server-side')) {
      detailsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const name = detailsForm.elements['name']?.value.trim();
        const phone = detailsForm.elements['phone']?.value.trim();
        const email = detailsForm.elements['email']?.value.trim();
        const pw = detailsForm.elements['password']?.value;
        const confirm = detailsForm.elements['confirm']?.value;
        const terms = detailsForm.elements['terms']?.checked;

        if (!name || !phone || !email || !pw) {
          window.vaiToast && window.vaiToast('Please complete all fields.', 'error');
          return;
        }
        if (pw.length < 6) {
          window.vaiToast && window.vaiToast('Password must be at least 6 characters.', 'error');
          return;
        }
        if (pw !== confirm) {
          window.vaiToast && window.vaiToast('Passwords do not match.', 'error');
          return;
        }
        if (!terms) {
          window.vaiToast && window.vaiToast('Please accept the terms to continue.', 'error');
          return;
        }
        // All good — go to OTP step
        state.phone = phone;
        const target = document.querySelector('[data-otp-phone]');
        if (target) {
          const masked = phone.slice(-4).padStart(phone.length, '•');
          target.textContent = masked;
        }
        window.vaiToast && window.vaiToast(`OTP sent to ${phone}`, 'success');
        setStep(2);
      });
    }

    const otpForm = document.querySelector('[data-reg-otp]');
    // [Django migration] Phase 4 OTP form lives on email_verify.html and uses
    // server-side validation. Old Phase 3 flow stays for any preview pages.
    if (otpForm && !otpForm.hasAttribute('data-server-side')) {
      otpForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const code = [...otpForm.querySelectorAll('[data-otp]')].map(i => i.value).join('');
        if (code.length !== 6) {
          window.vaiToast && window.vaiToast('Please enter all 6 digits.', 'error');
          return;
        }
        window.vaiToast && window.vaiToast('Account created. Welcome to the family.', 'success');
        setTimeout(() => location.href = '/profile.html', 700);
      });
    }
  }

  function wireGoogle() {
    document.querySelectorAll('[data-google]').forEach(btn => {
      btn.addEventListener('click', () => {
        window.vaiToast && window.vaiToast('Continuing with Google…', 'success');
        setTimeout(() => location.href = '/profile.html', 700);
      });
    });
  }

  function wireBack() {
    const back = document.querySelector('[data-reg-back]');
    if (!back) return;
    back.addEventListener('click', () => setStep(1));
  }

  function boot() {
    wirePw();
    wireOtpInputs();
    wireResend();
    wireForms();
    wireGoogle();
    wireBack();
    setStep(1);

    if (window.vaiAnimations) {
      const { scrollReveal } = window.vaiAnimations;
      requestAnimationFrame(() => scrollReveal('.auth-card', { y: 20 }));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
