/*
 * Dữ liệu không phụ thuộc ngôn ngữ: link, thứ tự hiển thị, icon và ảnh.
 * Chữ hiển thị nằm trong locales/vi.js và locales/en.js, tra theo `id`.
 * Thêm một mục mới = thêm vào mảng ở đây + thêm bản dịch cùng `id` ở cả hai file locale.
 */
(function () {
  var REPO = 'https://github.com/phamphuongquynh0307/Auto_PGsharp_byQpham';

  window.SITE = {
    languages: ['vi', 'en'],
    defaultLanguage: 'vi',
    storageKey: 'acp-lang',
    // URL công khai của trang (kết thúc bằng /). Dùng cho ảnh Open Graph khi đổi ngôn ngữ.
    siteUrl: 'https://phamphuongquynh0307.github.io/Auto_PGsharp_byQpham/',

    links: {
      github: REPO,
      download: REPO + '/releases/latest/download/AutoCatchPokemonPGSharp.exe',
      extension: 'https://raw.githubusercontent.com/phamphuongquynh0307/Auto_PGsharp_byQpham/master/downloads/discord-coord-collector-v0.3.3.zip',
      releases: REPO + '/releases/latest',
      license: REPO + '/blob/master/LICENSE',
      discord: 'https://discord.gg/QXSfKKPpG6',
      kofi: 'https://ko-fi.com/qpham7286',
    },

    badges: [
      { id: 'windows', icon: 'windows' },
      { id: 'adb', icon: 'android' },
      { id: 'wifi', icon: 'wifi' },
      { id: 'quickCatch', icon: 'zap' },
      { id: 'tests', icon: 'flask-conical' },
    ],

    // `featured: true` = thẻ rộng gấp đôi trên màn hình lớn.
    features: [
      { id: 'nearby', icon: 'radar' },
      { id: 'quickCatch', icon: 'zap', featured: true },
      { id: 'ballTracking', icon: 'crosshair' },
      { id: 'ivShiny', icon: 'sparkles', featured: true },
      { id: 'discordCoords', icon: 'map-pinned' },
      { id: 'autoWalk', icon: 'footprints' },
      { id: 'popups', icon: 'shield-check' },
      { id: 'ballSwitch', icon: 'refresh-cw' },
      { id: 'webhook', icon: 'bell-ring' },
      { id: 'screens', icon: 'scaling' },
    ],

    // `image` trỏ tới `id` trong mảng gallery bên dưới.
    modes: [
      { id: 'catch', icon: 'ball', image: 'catchLayout' },
      { id: 'feed', icon: 'sparkles', image: 'shundoFeed' },
      { id: 'coord', icon: 'map-pinned', image: 'coordFlow' },
      { id: 'spin', icon: 'route', image: 'spinPreview' },
    ],

    steps: [
      { id: 'usb', icon: 'bug' },
      { id: 'cable', icon: 'usb' },
      { id: 'wifi', icon: 'wifi' },
      { id: 'run', icon: 'play' },
    ],

    // Ảnh gốc: guide_images/<file>.png, đã nén sang assets/img/guide/<file>-480.webp và -1024.webp.
    gallery: [
      { id: 'appWindows', file: '01-app-windows' },
      { id: 'usbDebug', file: '02-usb-debug' },
      { id: 'connectWifi', file: '03-connect-wifi' },
      { id: 'testControl', file: '04-test-control' },
      { id: 'catchLayout', file: '08-catch-layout' },
      { id: 'shundoFeed', file: '10-shundo-feed' },
      { id: 'edgeExtension', file: '12-edge-extension' },
      { id: 'coordFlow', file: '14-coord-flow' },
      { id: 'spinPreview', file: '15-spin-preview' },
    ],
    imageSize: { width: 1024, height: 1536 },

    requirements: [
      { id: 'windows', icon: 'windows' },
      { id: 'android', icon: 'android' },
      { id: 'pgsharp', icon: 'gamepad-2' },
      { id: 'usbDebug', icon: 'bug' },
      { id: 'wifi', icon: 'wifi' },
      { id: 'cable', icon: 'cable' },
    ],

    faq: ['key', 'wifi', 'taps', 'balls', 'devices', 'discord', 'official'],
  };
})();
