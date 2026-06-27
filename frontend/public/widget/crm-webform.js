/* Встраиваемый виджет веб-формы PRVMS CRM.
 * Использование на сайте клиента:
 *   <script src="https://crm.example/widget/crm-webform.js"
 *           data-token="<uuid>" data-base="https://crm.example" async></script>
 * Скрипт подтягивает описание формы, рендерит поля и отправляет заявку.
 * Поддержаны типы полей: text, email, phone, textarea, select, checkbox.
 * Капча (reCAPTCHA/hCaptcha) подключается, если форма-схема содержит captcha.site_key.
 */
(function () {
  var tag = document.currentScript;
  if (!tag) return;
  var token = tag.getAttribute('data-token');
  var base = (tag.getAttribute('data-base') || '').replace(/\/+$/, '');
  if (!token || !base) return;

  var mount = document.createElement('div');
  mount.className = 'prvms-webform';
  tag.parentNode.insertBefore(mount, tag);

  var styles =
    '.prvms-webform{max-width:420px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}' +
    '.prvms-webform input,.prvms-webform textarea,.prvms-webform select{width:100%;box-sizing:border-box;padding:10px;margin:6px 0;' +
    'border:1px solid #d1d5db;border-radius:8px;font-size:14px}' +
    '.prvms-webform .prvms-check{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:14px}' +
    '.prvms-webform .prvms-check input{width:auto;margin:0}' +
    '.prvms-webform button{width:100%;padding:11px;margin-top:8px;border:0;border-radius:8px;background:#4f46e5;' +
    'color:#fff;font-size:15px;font-weight:600;cursor:pointer}' +
    '.prvms-webform button:disabled{opacity:.6;cursor:default}' +
    '.prvms-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}' +
    '.prvms-msg{padding:14px;border-radius:8px;background:#ecfdf5;color:#065f46;font-size:14px}';
  var styleEl = document.createElement('style');
  styleEl.textContent = styles;
  document.head.appendChild(styleEl);

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, data: j }; }); });
  }

  function loadCaptchaScript(provider) {
    var src = provider === 'hcaptcha'
      ? 'https://js.hcaptcha.com/1/api.js'
      : 'https://www.google.com/recaptcha/api.js';
    if (document.querySelector('script[src="' + src + '"]')) return;
    var s = document.createElement('script');
    s.src = src; s.async = true; s.defer = true;
    document.head.appendChild(s);
  }

  fetch(base + '/api/public/webform/' + token + '/schema/')
    .then(function (r) { return r.json(); })
    .then(function (schema) { render(schema); })
    .catch(function () { mount.textContent = 'Форма недоступна.'; });

  function render(schema) {
    var fields = (schema && schema.fields) || [];
    var captcha = schema && schema.captcha;
    var formEl = document.createElement('form');

    // honeypot
    var hp = document.createElement('input');
    hp.name = 'website'; hp.className = 'prvms-hp'; hp.tabIndex = -1; hp.autocomplete = 'off';
    formEl.appendChild(hp);

    var inputs = {};
    fields.forEach(function (f) {
      if (f.type === 'checkbox') {
        var wrap = document.createElement('label');
        wrap.className = 'prvms-check';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        if (f.required) cb.required = true;
        var span = document.createElement('span');
        span.textContent = f.label + (f.required ? ' *' : '');
        wrap.appendChild(cb); wrap.appendChild(span);
        formEl.appendChild(wrap);
        inputs[f.key] = cb;
        return;
      }
      var el;
      if (f.type === 'textarea') {
        el = document.createElement('textarea');
      } else if (f.type === 'select') {
        el = document.createElement('select');
        var ph = document.createElement('option');
        ph.value = ''; ph.textContent = f.label + (f.required ? ' *' : '');
        el.appendChild(ph);
        (f.options || []).forEach(function (opt) {
          var o = document.createElement('option');
          o.value = opt; o.textContent = opt;
          el.appendChild(o);
        });
        if (f.required) el.required = true;
      } else {
        el = document.createElement('input');
        el.type = f.type === 'email' ? 'email' : (f.type === 'phone' ? 'tel' : 'text');
      }
      if (f.type !== 'select') {
        el.placeholder = f.label + (f.required ? ' *' : '');
        if (f.required) el.required = true;
      }
      formEl.appendChild(el);
      inputs[f.key] = el;
    });

    // Капча (если форма требует её): рендерим контейнер провайдера.
    var captchaBox = null;
    if (captcha && captcha.site_key) {
      loadCaptchaScript(captcha.provider);
      captchaBox = document.createElement('div');
      captchaBox.className = captcha.provider === 'hcaptcha' ? 'h-captcha' : 'g-recaptcha';
      captchaBox.setAttribute('data-sitekey', captcha.site_key);
      captchaBox.style.margin = '8px 0';
      formEl.appendChild(captchaBox);
    }

    var btn = document.createElement('button');
    btn.type = 'submit';
    btn.textContent = 'Отправить';
    formEl.appendChild(btn);

    formEl.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var captchaToken = '';
      if (captcha && captcha.site_key) {
        try {
          captchaToken = captcha.provider === 'hcaptcha'
            ? (window.hcaptcha && window.hcaptcha.getResponse())
            : (window.grecaptcha && window.grecaptcha.getResponse());
        } catch (e) { captchaToken = ''; }
        if (!captchaToken) { btn.textContent = 'Подтвердите, что вы не робот'; return; }
      }
      btn.disabled = true;
      var payload = { website: hp.value, fields: {}, captcha: captchaToken };
      Object.keys(inputs).forEach(function (k) {
        var el = inputs[k];
        payload.fields[k] = el.type === 'checkbox' ? (el.checked ? 'Да' : '') : el.value;
      });
      post(base + '/api/public/webform/' + token + '/', payload)
        .then(function (res) {
          if (res.ok && res.data && res.data.status === 'ok') {
            var msg = document.createElement('div');
            msg.className = 'prvms-msg';
            msg.textContent = res.data.message || 'Спасибо! Мы свяжемся с вами.';
            mount.innerHTML = '';
            mount.appendChild(msg);
          } else {
            btn.disabled = false;
            btn.textContent = 'Попробовать снова';
          }
        })
        .catch(function () { btn.disabled = false; btn.textContent = 'Попробовать снова'; });
    });

    mount.appendChild(formEl);
  }
})();
