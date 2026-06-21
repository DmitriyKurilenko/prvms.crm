/* Встраиваемый виджет веб-формы PRVMS CRM.
 * Использование на сайте клиента:
 *   <script src="https://crm.example/widget/crm-webform.js"
 *           data-token="<uuid>" data-base="https://crm.example" async></script>
 * Скрипт подтягивает описание формы, рендерит поля и отправляет заявку.
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
    '.prvms-webform input,.prvms-webform textarea{width:100%;box-sizing:border-box;padding:10px;margin:6px 0;' +
    'border:1px solid #d1d5db;border-radius:8px;font-size:14px}' +
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

  fetch(base + '/api/public/webform/' + token + '/schema/')
    .then(function (r) { return r.json(); })
    .then(function (schema) { render(schema); })
    .catch(function () { mount.textContent = 'Форма недоступна.'; });

  function render(schema) {
    var fields = (schema && schema.fields) || [];
    var formEl = document.createElement('form');

    // honeypot
    var hp = document.createElement('input');
    hp.name = 'website'; hp.className = 'prvms-hp'; hp.tabIndex = -1; hp.autocomplete = 'off';
    formEl.appendChild(hp);

    var inputs = {};
    fields.forEach(function (f) {
      var el = f.type === 'textarea' ? document.createElement('textarea') : document.createElement('input');
      if (f.type !== 'textarea') {
        el.type = f.type === 'email' ? 'email' : (f.type === 'phone' ? 'tel' : 'text');
      }
      el.placeholder = f.label + (f.required ? ' *' : '');
      if (f.required) el.required = true;
      formEl.appendChild(el);
      inputs[f.key] = el;
    });

    var btn = document.createElement('button');
    btn.type = 'submit';
    btn.textContent = 'Отправить';
    formEl.appendChild(btn);

    formEl.addEventListener('submit', function (ev) {
      ev.preventDefault();
      btn.disabled = true;
      var payload = { website: hp.value, fields: {} };
      Object.keys(inputs).forEach(function (k) { payload.fields[k] = inputs[k].value; });
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
