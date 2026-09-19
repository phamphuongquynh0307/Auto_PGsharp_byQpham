/*
 * Auto Catch Pokémon cho PGSharp — logic trang.
 * Script thường (không phải ES module) để mở trực tiếp index.html từ máy vẫn chạy.
 *
 * Quy ước i18n trong HTML:
 *   data-i18n="khoa.con"              -> nội dung chữ (hỗ trợ **đậm** và `mã`)
 *   data-i18n-vars='{"n":1}'          -> biến thay cho {n} trong chuỗi
 *   data-i18n-attr="aria-label:khoa"  -> thuộc tính (nhiều mục cách nhau bằng |)
 *   data-i18n-list="khoa.mang"        -> render lại danh sách <li>/<p> từ một mảng chuỗi
 *   data-icon="ten"                   -> chèn SVG từ icons.js
 *   data-link="ten"                   -> href lấy từ SITE.links trong data.js
 */
(function () {
  'use strict';

  var I18N = window.I18N || {};
  var SITE = window.SITE;
  var ICONS = window.ICONS || {};
  var LANGS = SITE.languages;
  var DEFAULT_LANG = SITE.defaultLanguage;
  var root = document.documentElement;
  var lang = DEFAULT_LANG;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  // ---------------------------------------------------------------- helpers
  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  function lookup(obj, path) {
    return path.split('.').reduce(function (o, k) { return o == null ? undefined : o[k]; }, obj);
  }

  function t(key, vars) {
    var value = lookup(I18N[lang], key);
    if (value === undefined) {
      console.warn('[i18n] Thiếu khóa "' + key + '" cho ngôn ngữ ' + lang);
      value = lookup(I18N[DEFAULT_LANG], key);
      if (value === undefined) return '';
    }
    if (typeof value === 'string' && vars) {
      value = value.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? String(vars[k]) : m; });
    }
    return value;
  }

  function h(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === 'class') node.className = v;
        else if (k === 'text') node.textContent = v;
        else if (k === 'dataset') Object.keys(v).forEach(function (d) { node.dataset[d] = v[d]; });
        else node.setAttribute(k, v === true ? '' : v);
      });
    }
    (children || []).forEach(function (c) {
      if (c) node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return node;
  }

  function svg(name) {
    var icon = ICONS[name];
    if (!icon) { console.warn('[icons] Không có icon "' + name + '"'); return ''; }
    var paint = icon.type === 'fill'
      ? 'fill="currentColor"'
      : 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" ' + paint + ' aria-hidden="true" focusable="false">' + icon.body + '</svg>';
  }

  function iconEl(name, cls) {
    return h('span', { class: cls || 'icon', dataset: { icon: name } });
  }

  // **đậm** và `mã` -> <strong>/<code>, phần còn lại là text thuần (không dùng innerHTML).
  function setRich(node, text) {
    node.textContent = '';
    String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach(function (part) {
      if (!part) return;
      if (part.slice(0, 2) === '**' && part.slice(-2) === '**') node.appendChild(h('strong', { text: part.slice(2, -2) }));
      else if (part[0] === '`' && part.slice(-1) === '`') node.appendChild(h('code', { text: part.slice(1, -1) }));
      else node.appendChild(document.createTextNode(part));
    });
  }

  function renderIcons(ctx) {
    $$('[data-icon]', ctx).forEach(function (node) {
      if (!node.firstElementChild) node.innerHTML = svg(node.dataset.icon);
    });
  }

  function storageGet() {
    try { return window.localStorage.getItem(SITE.storageKey); } catch (e) { return null; }
  }
  function storageSet(value) {
    try { window.localStorage.setItem(SITE.storageKey, value); } catch (e) { /* chế độ riêng tư: bỏ qua */ }
  }

  // Kiểm tra hai file locale có cùng cấu trúc khóa (chỉ cảnh báo trong Console).
  function checkParity() {
    function walk(a, b, path) {
      Object.keys(a).forEach(function (k) {
        var p = path ? path + '.' + k : k;
        if (!(k in b)) console.warn('[i18n] Khóa "' + p + '" có trong một ngôn ngữ nhưng thiếu ở ngôn ngữ kia');
        else if (a[k] && typeof a[k] === 'object' && !Array.isArray(a[k])) walk(a[k], b[k], p);
      });
    }
    if (I18N.vi && I18N.en) { walk(I18N.vi, I18N.en, ''); walk(I18N.en, I18N.vi, ''); }
  }

  // ---------------------------------------------------------------- language
  function langFromUrl() {
    try {
      var value = new URLSearchParams(window.location.search).get('lang');
      return LANGS.indexOf(value) !== -1 ? value : null;
    } catch (e) { return null; }
  }

  function detectLanguage() {
    var fromUrl = langFromUrl();
    if (fromUrl) return fromUrl;
    var stored = storageGet();
    if (LANGS.indexOf(stored) !== -1) return stored;
    var prefs = navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language];
    for (var i = 0; i < prefs.length; i++) {
      var base = String(prefs[i] || '').toLowerCase().split('-')[0];
      if (LANGS.indexOf(base) !== -1) return base;
    }
    return DEFAULT_LANG;
  }

  function setMeta(selector, value) {
    var node = document.head.querySelector(selector);
    if (node) node.setAttribute('content', value);
  }

  function updateMeta() {
    var meta = t('meta');
    var image = SITE.siteUrl + meta.ogImage;
    var other = LANGS.filter(function (l) { return l !== lang; })[0];
    root.lang = lang;
    document.title = meta.title;
    setMeta('meta[name="description"]', meta.description);
    setMeta('meta[property="og:site_name"]', meta.siteName);
    setMeta('meta[property="og:title"]', meta.title);
    setMeta('meta[property="og:description"]', meta.description);
    setMeta('meta[property="og:locale"]', meta.ogLocale);
    setMeta('meta[property="og:locale:alternate"]', lookup(I18N[other], 'meta.ogLocale'));
    setMeta('meta[property="og:image"]', image);
    setMeta('meta[property="og:image:alt"]', meta.ogImageAlt);
    setMeta('meta[name="twitter:title"]', meta.title);
    setMeta('meta[name="twitter:description"]', meta.description);
    setMeta('meta[name="twitter:image"]', image);
  }

  function translate(ctx) {
    $$('[data-i18n]', ctx).forEach(function (node) {
      var vars = node.dataset.i18nVars ? JSON.parse(node.dataset.i18nVars) : null;
      setRich(node, t(node.dataset.i18n, vars));
    });
    $$('[data-i18n-attr]', ctx).forEach(function (node) {
      node.dataset.i18nAttr.split('|').forEach(function (pair) {
        var i = pair.indexOf(':');
        var vars = node.dataset.i18nVars ? JSON.parse(node.dataset.i18nVars) : null;
        node.setAttribute(pair.slice(0, i).trim(), t(pair.slice(i + 1).trim(), vars));
      });
    });
    $$('[data-i18n-list]', ctx).forEach(function (node) {
      var items = t(node.dataset.i18nList) || [];
      var tag = node.dataset.i18nItem || 'li';
      var withIcon = node.dataset.i18nIcon;
      node.textContent = '';
      items.forEach(function (text) {
        var item = h(tag);
        var span = h('span');
        setRich(span, text);
        if (withIcon) item.appendChild(iconEl(withIcon));
        item.appendChild(span);
        node.appendChild(item);
      });
      renderIcons(node);
    });
  }

  function applyLanguage(next, opts) {
    opts = opts || {};
    lang = LANGS.indexOf(next) !== -1 ? next : DEFAULT_LANG;
    translate(document);
    updateMeta();
    syncMenuLabel();
    syncGalleryLabels();
    if (lightbox.index !== null) lightbox.render();

    $$('.lang-switch [data-lang]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.dataset.lang === lang));
    });

    if (opts.persist) {
      storageSet(lang);
      // Nếu URL đang có ?lang= thì cập nhật theo, không tải lại trang.
      if (langFromUrl()) {
        try {
          var url = new URL(window.location.href);
          url.searchParams.set('lang', lang);
          window.history.replaceState(null, '', url);
        } catch (e) { /* file:// cũ: bỏ qua */ }
      }
    }
    if (opts.announce) {
      var live = $('#live-region');
      live.textContent = '';
      window.setTimeout(function () { live.textContent = t('common.languageChanged'); }, 60);
    }
  }

  // ---------------------------------------------------------------- render sections
  function renderBadges() {
    var list = $('#hero-badges');
    SITE.badges.forEach(function (b) {
      list.appendChild(h('li', { class: 'badge' + (b.id === 'tests' ? ' badge-yellow' : '') }, [
        iconEl(b.icon),
        h('span', { 'data-i18n': 'hero.badges.' + b.id }),
      ]));
    });
  }

  function renderFeatures() {
    var grid = $('#feature-grid');
    SITE.features.forEach(function (f, i) {
      var key = 'features.items.' + f.id;
      grid.appendChild(h('li', {
        class: 'feature-card' + (f.featured ? ' is-featured' : ''),
        'data-reveal': true,
        style: '--reveal-delay:' + (i % 4) * 70 + 'ms',
      }, [
        h('span', { class: 'feature-icon' }, [iconEl(f.icon)]),
        h('h3', { 'data-i18n': key + '.title' }),
        h('p', { 'data-i18n': key + '.text' }),
      ]));
    });
  }

  function galleryIndex(id) {
    for (var i = 0; i < SITE.gallery.length; i++) if (SITE.gallery[i].id === id) return i;
    return -1;
  }

  function imageSrc(file, width) { return 'assets/img/guide/' + file + '-' + width + '.webp'; }
  function imageSrcset(file) { return imageSrc(file, 480) + ' 480w, ' + imageSrc(file, 1024) + ' 1024w'; }

  function renderModes() {
    var tabs = $('#mode-tabs');
    var panels = $('#mode-panels');
    var mock = $('#mock-modes');

    SITE.modes.forEach(function (m, i) {
      var key = 'modes.items.' + m.id;
      var selected = i === 0;
      var img = SITE.gallery[galleryIndex(m.image)];

      tabs.appendChild(h('button', {
        type: 'button',
        class: 'mode-tab',
        role: 'tab',
        id: 'mode-tab-' + m.id,
        'aria-selected': String(selected),
        'aria-controls': 'mode-panel-' + m.id,
        tabindex: selected ? '0' : '-1',
        dataset: { mode: m.id },
      }, [
        h('span', { class: 'mode-tab-icon' }, [iconEl(m.icon)]),
        h('span', { 'data-i18n': key + '.tab' }),
        h('span', { class: 'mode-tab-num', 'aria-hidden': 'true', text: '0' + (i + 1) }),
      ]));

      panels.appendChild(h('div', {
        class: 'mode-panel',
        role: 'tabpanel',
        id: 'mode-panel-' + m.id,
        'aria-labelledby': 'mode-tab-' + m.id,
        tabindex: '0',
        hidden: !selected,
      }, [
        h('div', null, [
          h('h3', { 'data-i18n': key + '.tab' }),
          h('p', { class: 'mode-summary', 'data-i18n': key + '.summary' }),
          h('h4', { class: 'mode-prepare', 'data-i18n': 'modes.prepareTitle' }),
          h('ul', { class: 'check-list', 'data-i18n-list': key + '.points', 'data-i18n-icon': 'check' }),
        ]),
        h('button', {
          type: 'button',
          class: 'mode-image',
          dataset: { gallery: m.image },
          'data-i18n-attr': 'aria-label:modes.viewImage',
        }, [
          h('img', {
            src: imageSrc(img.file, 480),
            srcset: imageSrcset(img.file),
            sizes: '(min-width: 768px) 250px, 320px',
            width: SITE.imageSize.width,
            height: SITE.imageSize.height,
            loading: 'lazy',
            decoding: 'async',
            'data-i18n-attr': 'alt:gallery.items.' + m.image + '.alt',
          }),
          h('span', { class: 'zoom-hint', 'aria-hidden': 'true' }, [iconEl('maximize-2')]),
        ]),
      ]));

      mock.appendChild(h('li', { class: selected ? 'active' : null }, [
        h('span', { dataset: { icon: m.icon } }),
        h('span', { 'data-i18n': key + '.tab' }),
      ]));
    });
  }

  function renderSteps() {
    var list = $('#timeline');
    SITE.steps.forEach(function (s, i) {
      var key = 'setup.steps.' + s.id;
      list.appendChild(h('li', { class: 'step', 'data-reveal': true, style: '--reveal-delay:' + i * 90 + 'ms' }, [
        h('span', { class: 'step-num', 'aria-hidden': 'true', text: String(i + 1) }),
        h('div', { class: 'step-body' }, [
          h('p', { class: 'step-label' }, [
            iconEl(s.icon),
            h('span', { 'data-i18n': 'setup.stepLabel', 'data-i18n-vars': JSON.stringify({ n: i + 1 }) }),
          ]),
          h('h3', { 'data-i18n': key + '.title' }),
          h('p', { 'data-i18n': key + '.text' }),
        ]),
      ]));
    });
  }

  function renderGallery() {
    var track = $('#carousel-track');
    SITE.gallery.forEach(function (g, i) {
      var key = 'gallery.items.' + g.id;
      track.appendChild(h('li', { class: 'gallery-item' }, [
        h('figure', null, [
          h('button', {
            type: 'button',
            class: 'gallery-thumb',
            dataset: { gallery: g.id },
          }, [
            h('img', {
              src: imageSrc(g.file, 480),
              srcset: imageSrcset(g.file),
              sizes: '(min-width: 1024px) 280px, 72vw',
              width: SITE.imageSize.width,
              height: SITE.imageSize.height,
              loading: 'lazy',
              decoding: 'async',
              'data-i18n-attr': 'alt:' + key + '.alt',
            }),
            h('span', { class: 'zoom-hint', 'aria-hidden': 'true' }, [iconEl('maximize-2')]),
          ]),
          h('figcaption', { class: 'gallery-caption' }, [
            h('span', { 'aria-hidden': 'true', text: (i < 9 ? '0' : '') + (i + 1) }),
            h('span', { 'data-i18n': key + '.caption' }),
          ]),
        ]),
      ]));
    });
  }

  // Nhãn nút phóng to ghép caption của ngôn ngữ hiện tại.
  function syncGalleryLabels() {
    $$('.gallery-thumb').forEach(function (btn) {
      btn.setAttribute('aria-label', t('gallery.open', { caption: t('gallery.items.' + btn.dataset.gallery + '.caption') }));
    });
  }

  function renderRequirements() {
    var grid = $('#req-grid');
    SITE.requirements.forEach(function (r, i) {
      var key = 'requirements.items.' + r.id;
      grid.appendChild(h('li', { class: 'req-item', 'data-reveal': true, style: '--reveal-delay:' + (i % 3) * 70 + 'ms' }, [
        h('span', { class: 'req-icon' }, [iconEl(r.icon)]),
        h('div', null, [
          h('h3', { 'data-i18n': key + '.title' }),
          h('p', { 'data-i18n': key + '.text' }),
        ]),
      ]));
    });
  }

  function renderFaq() {
    var list = $('#faq-list');
    SITE.faq.forEach(function (id, i) {
      var key = 'faq.items.' + id;
      list.appendChild(h('div', { class: 'faq-item', 'data-reveal': true, style: '--reveal-delay:' + Math.min(i, 3) * 60 + 'ms' }, [
        h('h3', null, [
          h('button', {
            type: 'button',
            class: 'faq-trigger',
            id: 'faq-q-' + id,
            'aria-expanded': 'false',
            'aria-controls': 'faq-a-' + id,
          }, [
            h('span', { 'data-i18n': key + '.q' }),
            h('span', { class: 'faq-chevron', 'aria-hidden': 'true' }, [iconEl('chevron-down')]),
          ]),
        ]),
        h('div', { class: 'faq-panel', id: 'faq-a-' + id, role: 'region', 'aria-labelledby': 'faq-q-' + id, inert: true }, [
          h('div', null, [
            h('div', { class: 'faq-answer', 'data-i18n-list': key + '.a', 'data-i18n-item': 'p' }),
          ]),
        ]),
      ]));
    });
  }

  function wireLinks() {
    $$('[data-link]').forEach(function (a) {
      var href = SITE.links[a.dataset.link];
      if (href) a.setAttribute('href', href);
      else console.warn('[links] Không có link "' + a.dataset.link + '"');
    });
    // Mọi link mở tab mới đều báo cho trình đọc màn hình biết.
    $$('a[target="_blank"]').forEach(function (a) {
      a.setAttribute('rel', 'noopener noreferrer');
      if (!a.querySelector('[data-i18n="common.newTab"]')) {
        a.appendChild(h('span', { class: 'sr-only', 'data-i18n': 'common.newTab' }));
      }
    });
  }

  // ---------------------------------------------------------------- interactions
  function initLanguageSwitch() {
    $$('.lang-switch [data-lang]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.dataset.lang === lang) return;
        applyLanguage(btn.dataset.lang, { persist: true, announce: true });
      });
    });
  }

  var header = $('#site-header');
  var menuToggle = $('#menu-toggle');
  var mobileMenu = $('#mobile-menu');

  function syncMenuLabel() {
    var open = menuToggle.getAttribute('aria-expanded') === 'true';
    menuToggle.setAttribute('aria-label', t(open ? 'nav.closeMenu' : 'nav.openMenu'));
  }

  function setMenu(open, restoreFocus) {
    menuToggle.setAttribute('aria-expanded', String(open));
    mobileMenu.hidden = !open;
    header.classList.toggle('menu-open', open);
    syncMenuLabel();
    if (open) { var first = $('a', mobileMenu); if (first) first.focus(); }
    else if (restoreFocus) menuToggle.focus();
  }

  function initHeader() {
    var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    menuToggle.addEventListener('click', function () {
      setMenu(menuToggle.getAttribute('aria-expanded') !== 'true', false);
    });
    mobileMenu.addEventListener('click', function (e) {
      if (e.target.closest('a')) setMenu(false, false);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !mobileMenu.hidden) setMenu(false, true);
    });
    window.matchMedia('(min-width: 1200px)').addEventListener('change', function (mq) {
      if (mq.matches && !mobileMenu.hidden) setMenu(false, false);
    });

    // Đánh dấu mục menu đang xem.
    if (!('IntersectionObserver' in window)) return;
    var links = $$('[data-nav]');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) {
          if (a.dataset.nav === entry.target.id) a.setAttribute('aria-current', 'true');
          else a.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    ['features', 'modes', 'setup', 'gallery', 'faq'].forEach(function (id) { io.observe(document.getElementById(id)); });
    // Ra khỏi các mục có trong menu thì bỏ đánh dấu.
    var clear = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) links.forEach(function (a) { a.removeAttribute('aria-current'); });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    ['top', 'requirements', 'download', 'community'].forEach(function (id) { clear.observe(document.getElementById(id)); });
  }

  function initTabs() {
    var tabs = $$('.mode-tab');
    var mock = $$('#mock-modes li');

    function select(tab, focus) {
      tabs.forEach(function (t2, i) {
        var on = t2 === tab;
        t2.setAttribute('aria-selected', String(on));
        t2.tabIndex = on ? 0 : -1;
        document.getElementById(t2.getAttribute('aria-controls')).hidden = !on;
        if (mock[i]) mock[i].classList.toggle('active', on);
      });
      if (focus) tab.focus();
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { select(tab, false); });
      tab.addEventListener('keydown', function (e) {
        var next = null;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = tabs[(i + 1) % tabs.length];
        else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = tabs[(i - 1 + tabs.length) % tabs.length];
        else if (e.key === 'Home') next = tabs[0];
        else if (e.key === 'End') next = tabs[tabs.length - 1];
        if (next) { e.preventDefault(); select(next, true); }
      });
    });
  }

  function initFaq() {
    $$('.faq-trigger').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var open = btn.getAttribute('aria-expanded') !== 'true';
        var panel = document.getElementById(btn.getAttribute('aria-controls'));
        btn.setAttribute('aria-expanded', String(open));
        btn.closest('.faq-item').classList.toggle('is-open', open);
        if (open) panel.removeAttribute('inert');
        else panel.setAttribute('inert', '');
      });
    });
  }

  function initCarousel() {
    var track = $('#carousel-track');
    var prev = $('#carousel-prev');
    var next = $('#carousel-next');

    function update() {
      var max = track.scrollWidth - track.clientWidth - 2;
      prev.disabled = track.scrollLeft <= 2;
      next.disabled = track.scrollLeft >= max;
    }
    function step(dir) {
      var item = $('.gallery-item', track);
      var amount = item ? (item.getBoundingClientRect().width + 16) * Math.max(1, Math.floor(track.clientWidth / item.getBoundingClientRect().width) - 1) : track.clientWidth * 0.8;
      track.scrollBy({ left: dir * amount, behavior: reduceMotion.matches ? 'auto' : 'smooth' });
    }
    prev.addEventListener('click', function () { step(-1); });
    next.addEventListener('click', function () { step(1); });
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  }

  // ---------------------------------------------------------------- lightbox
  var lightbox = {
    index: null,
    dialog: null,
    open: function (index) {
      this.index = index;
      this.render();
      if (!this.dialog.open) {
        if (typeof this.dialog.showModal === 'function') this.dialog.showModal();
        else this.dialog.setAttribute('open', '');
      }
      $('#lightbox-close').focus();
    },
    move: function (delta) {
      var n = SITE.gallery.length;
      this.index = (this.index + delta + n) % n;
      this.render();
    },
    render: function () {
      var g = SITE.gallery[this.index];
      var img = $('#lightbox-img');
      img.src = imageSrc(g.file, 1024);
      img.alt = t('gallery.items.' + g.id + '.alt');
      $('#lightbox-caption').textContent = t('gallery.items.' + g.id + '.caption');
      $('#lightbox-counter').textContent = t('gallery.counter', { current: this.index + 1, total: SITE.gallery.length });
    },
  };

  function initLightbox() {
    var dialog = $('#lightbox');
    lightbox.dialog = dialog;

    document.addEventListener('click', function (e) {
      var trigger = e.target.closest('[data-gallery]');
      if (trigger) lightbox.open(galleryIndex(trigger.dataset.gallery));
    });
    $('#lightbox-close').addEventListener('click', function () { dialog.close(); });
    $('#lightbox-prev').addEventListener('click', function () { lightbox.move(-1); });
    $('#lightbox-next').addEventListener('click', function () { lightbox.move(1); });
    dialog.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { e.preventDefault(); lightbox.move(-1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); lightbox.move(1); }
    });
    // Bấm ra vùng tối bên ngoài để đóng.
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () { lightbox.index = null; });
  }

  // ---------------------------------------------------------------- reveal on scroll
  function initReveal() {
    var nodes = $$('[data-reveal]');
    if (reduceMotion.matches || !('IntersectionObserver' in window)) {
      nodes.forEach(function (n) { n.classList.add('is-visible'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); io.unobserve(entry.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    nodes.forEach(function (n) { io.observe(n); });
  }

  // ---------------------------------------------------------------- boot
  function boot() {
    checkParity();
    renderBadges();
    renderFeatures();
    renderModes();
    renderSteps();
    renderGallery();
    renderRequirements();
    renderFaq();
    wireLinks();
    renderIcons(document);

    initHeader();
    initLightbox();
    applyLanguage(detectLanguage(), { persist: false });

    initLanguageSwitch();
    initTabs();
    initFaq();
    initCarousel();
    initReveal();

    root.classList.remove('i18n-pending');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
