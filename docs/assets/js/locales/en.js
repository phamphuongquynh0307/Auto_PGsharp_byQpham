/*
 * English translations.
 * - Keep exactly the same keys as vi.js (app.js logs a Console warning for any mismatch).
 * - **bold** and `code` are rendered as formatting; do not put HTML in strings.
 * - Content must follow README.md / HUONG_DAN.md; do not add figures or features the repo does not have.
 */
window.I18N = window.I18N || {};
window.I18N.en = {
  meta: {
    title: 'Auto Catch Pokémon for PGSharp – Windows automation over ADB',
    description:
      'A Windows tool that controls Android devices through ADB: automatic catching, keyless Quick Catch, IV-based shiny checking, Discord coordinates and PokéStop spinning.',
    ogLocale: 'en_US',
    ogImage: 'og-image-en.png',
    ogImageAlt: 'Auto Catch Pokémon for PGSharp – a Windows tool that controls Android phones over ADB',
    siteName: 'Auto Catch Pokémon for PGSharp',
  },

  common: {
    skipToContent: 'Skip to main content',
    newTab: '(opens in a new tab)',
    languageGroup: 'Choose language',
    languageChanged: 'Switched to English',
    backToTop: 'Back to top',
    homeLabel: 'Auto Catch Pokémon for PGSharp, back to top',
    brandSub: 'for PGSharp',
  },

  nav: {
    label: 'Main navigation',
    features: 'Features',
    modes: 'Modes',
    setup: 'Setup',
    gallery: 'Gallery',
    faq: 'FAQ',
    download: 'Download latest version',
    openMenu: 'Open menu',
    closeMenu: 'Close menu',
  },

  hero: {
    eyebrow: 'Independent project · Source available',
    titleLead: 'Automate Pokémon Catching',
    titleAccent: 'on PGSharp',
    description:
      'A Windows tool that controls Android devices through ADB, with support for regular catching, keyless Quick Catch, IV-based shiny checking, Discord coordinates and automatic PokéStop spinning.',
    ctaDownload: 'Download for Windows',
    ctaGithub: 'View on GitHub',
    ctaGuide: 'Read the guide',
    badgesLabel: 'Highlights',
    badges: {
      windows: 'Windows',
      adb: 'Android + ADB',
      wifi: 'Wi-Fi Connection',
      quickCatch: 'Keyless Quick Catch',
      tests: '327+ automated tests',
    },
    disclaimer: 'Not an official product. Not affiliated with Niantic, The Pokémon Company or PGSharp.',
    mockup: {
      label: 'Illustration: a Windows app controlling an Android phone over wireless ADB',
      caption: 'Illustrative interface',
      device: 'Android device',
      connected: 'Connected over Wi-Fi',
      modes: 'Modes',
      ivTarget: 'Target IV',
      ivAtk: 'Atk',
      ivDef: 'Def',
      ivHp: 'HP',
      log: 'Log',
      run: 'Run',
      pause: 'Pause',
      stop: 'Stop',
      link: 'ADB · Wi-Fi',
      nearby: 'Nearby',
    },
  },

  features: {
    eyebrow: 'Features',
    title: 'Hand off the repetitive work',
    intro:
      'The app reads the phone screen in real time, recognises the PGSharp interface and sends touch input over ADB.',
    items: {
      nearby: {
        title: 'Catch from Nearby',
        text: 'Automatically catch Pokémon from the Nearby list: open the encounter, throw, then return to the map for the next one.',
      },
      quickCatch: {
        title: 'Keyless Quick Catch',
        text: 'Use Quick Catch without a paid PGSharp key — Android touch control throws the ball and leaves the encounter fast.',
      },
      ballTracking: {
        title: 'Real ball tracking',
        text: 'Detect the real ball position on the encounter screen and adjust throw coordinates to match. Manual calibration is still available.',
      },
      ivShiny: {
        title: 'Exact-IV shiny checks',
        text: 'Check shiny Pokémon against exact Attack, Defense and HP IV values from 0 to 15. The bot stops only when all three match.',
      },
      discordCoords: {
        title: 'Coordinates from Discord',
        text: 'Receive Pokémon coordinates from Discord through an Edge extension. The next one is requested only after the current check finishes.',
      },
      autoWalk: {
        title: 'AutoWalk and PokéStop spinning',
        text: 'Maintain AutoWalk and automatically spin unspun PokéStops inside the scanning ring around your avatar.',
      },
      popups: {
        title: 'Safe popup handling',
        text: 'Close weather, speed, level-up and PokéStop screens. Android dialogs must show an exact CANCEL button before anything is tapped.',
      },
      ballSwitch: {
        title: 'Great and Ultra Ball fallback',
        text: 'When regular Poké Balls run out, the ball picker is opened and the next available type is used. The bag is only reported empty when nothing is left.',
      },
      webhook: {
        title: 'Discord alerts',
        text: 'Send alerts and periodic reports through Discord webhooks: long spawn gaps, low battery, no balls, shiny encounters and more.',
      },
      screens: {
        title: 'Screen adaptation',
        text: 'Adapt coordinates to each Android screen size and DPI, with no need to force a specific resolution.',
      },
    },
  },

  modes: {
    eyebrow: 'Operating modes',
    title: 'Four modes, one app',
    intro: 'Each mode expects its own PGSharp layout. Pick a mode, follow its checklist, then press Run.',
    tabsLabel: 'Choose an operating mode',
    prepareTitle: 'Before you start',
    viewImage: 'Enlarge guide image',
    items: {
      catch: {
        tab: 'Automatic Pokémon Catching',
        summary: 'Select Pokémon from the Nearby list and automate the catching process.',
        points: [
          'Two catch styles: **Regular Catch** watches the result and throws again if the Pokémon breaks out; **Quick Catch** needs no PGSharp key.',
          'Keep the Nearby bar visible on the right, and make sure no PGSharp menu covers the first Pokémon.',
          'For your first run, set the **catch limit to 1** and watch one full cycle before raising it.',
        ],
      },
      feed: {
        tab: 'IV Shiny Checking from Feed',
        summary: 'Check each Pokémon and stop only when a shiny matches all three target IV values.',
        points: [
          'Turn on **Block Non-Shiny** in PGSharp so that encounters only open for shinies.',
          'Open the Feed with the RSS icon and keep the Nearby bar with its `@` marker visible.',
          'If the IV cannot be read with certainty, the app keeps the encounter and pauses instead of skipping it.',
          'Disconnect Go Plus before starting — while it is connected, PGSharp blocks teleports.',
        ],
      },
      coord: {
        tab: 'Shundo Hunting from Discord Coordinates',
        summary: 'Receive coordinates from the Edge extension, teleport sequentially and process each Pokémon.',
        points: [
          'Install **Discord Coord Collector** in Edge and sign in to Discord Web and Pokedex100 in the same profile.',
          'Keep the PGSharp shortcut menu open and calibrate three points: the Teleport row, the Coordinates box and the OK button.',
          'Open the app and press **Run** first, then press the Start button in the Collector popup.',
          'Turn on Block Non-Shiny and disconnect Go Plus, just like the Feed mode.',
        ],
      },
      spin: {
        tab: 'PokéStop Spinning While Walking',
        summary: 'Keep AutoWalk active and spin eligible PokéStops within the scanning area.',
        points: [
          'The default scanning ring has a 450 px radius, with 2 seconds between taps.',
          'Only blue, unspun PokéStops inside the ring are tapped; purple stops that were already spun are skipped.',
          'When PGSharp asks **Stop AutoWalk?**, the app always chooses CANCEL and closes PokéStop screens with the X button.',
        ],
      },
    },
  },

  setup: {
    eyebrow: 'Setup',
    title: 'How it works',
    intro: 'You only need a USB cable the first time. After that, the app reconnects over Wi-Fi.',
    stepLabel: 'Step {n}',
    steps: {
      usb: {
        title: 'Enable USB debugging on the Android device',
        text: 'Go to **Settings → About phone**, tap **Build number** seven times, then turn on **USB debugging** in Developer options.',
      },
      cable: {
        title: 'Connect the phone by USB for the initial setup',
        text: 'Use a data-capable cable, open the app, click **Connect** and allow USB debugging when Android asks.',
      },
      wifi: {
        title: 'The app switches to wireless ADB and remembers the device',
        text: 'Unplug the cable once the app says it is safe to do so. Next time, just select the saved phone.',
      },
      run: {
        title: 'Select an operating mode and press Run',
        text: 'Keep Pokémon GO on the map screen, choose a mode and catch style, press **Run** and follow along in the log panel.',
      },
    },
    note: 'The phone and computer must be connected to the same Wi-Fi network.',
    guideLink: 'Read the full setup guide on GitHub',
    guideUrl: 'https://github.com/phamphuongquynh0307/Auto_PGsharp_byQpham#getting-started',
  },

  gallery: {
    eyebrow: 'Gallery',
    title: 'Visual setup guide',
    intro: 'Step-by-step images from the guide built into the app. The images are labelled in Vietnamese. Select one to enlarge it.',
    regionLabel: 'Guide images',
    open: 'Enlarge: {caption}',
    prev: 'Previous image',
    next: 'Next image',
    scrollPrev: 'Scroll to earlier images',
    scrollNext: 'Scroll to later images',
    close: 'Close',
    counter: 'Image {current} of {total}',
    items: {
      appWindows: {
        caption: 'Download from Releases',
        alt: 'Three install steps: download AutoCatchPokemonPGSharp.exe from the Releases page, move it to its own writable folder and choose Run anyway if SmartScreen warns.',
      },
      usbDebug: {
        caption: 'Enable USB debugging',
        alt: 'Three Android screens: open About phone, tap Build number seven times and switch on USB debugging in Developer options.',
      },
      connectWifi: {
        caption: 'Connect over Wi-Fi',
        alt: 'Plug in the USB cable and allow debugging, choose the Wi-Fi option and click Connect; the log confirms Wi-Fi is connected and the cable can be removed.',
      },
      testControl: {
        caption: 'Test ADB and scrcpy',
        alt: 'Select the device, run the ADB/scrcpy test, wait for three success lines, then open the live view window.',
      },
      catchLayout: {
        caption: 'Layout for automatic catching',
        alt: 'Correct PGSharp screen for automatic catching: Nearby bar on the right, first Pokémon at the top, the @ marker uncovered and no menu blocking the target.',
      },
      shundoFeed: {
        caption: 'Shiny checking from Feed',
        alt: 'Turn on Block Non-Shiny, Encounter IV and Quick Load Map; open the Feed with the RSS icon, keep the Nearby @ bar visible and disconnect Virtual Go Plus.',
      },
      edgeExtension: {
        caption: 'Install the Edge extension',
        alt: 'Extract Discord Coord Collector, open edge://extensions, enable Developer mode, choose Load unpacked, then open the Coord Collector popup.',
      },
      coordFlow: {
        caption: 'Discord coordinate flow',
        alt: 'Calibrate the Teleport, Coordinates and OK points; open the app first, then press Start in the Collector. Flow: Collector, app, teleport, check complete, next coordinate.',
      },
      spinPreview: {
        caption: 'PokéStop spinning while walking',
        alt: 'Keep AutoWalk in the shortcuts and check the scanning ring: blue stops are tapped, purple or out-of-range stops are skipped, and the Stop AutoWalk popup is always cancelled.',
      },
    },
  },

  requirements: {
    eyebrow: 'System requirements',
    title: 'What you need',
    intro: 'Have everything below ready before your first run.',
    items: {
      windows: { title: 'Windows computer', text: 'Runs AutoCatchPokemonPGSharp.exe from its own writable folder.' },
      android: { title: 'Android phone', text: 'Keep the same resolution and DPI after calibrating.' },
      pgsharp: { title: 'Pokémon GO with PGSharp', text: 'Open it and wait on the map screen before starting.' },
      usbDebug: { title: 'USB debugging enabled', text: 'Found in Android Developer options.' },
      wifi: { title: 'Both devices on the same Wi-Fi network', text: 'Turn off VPN or AP isolation if the devices cannot see each other.' },
      cable: { title: 'USB cable for the initial connection', text: 'It must carry data — charge-only cables will not work.' },
    },
  },

  download: {
    eyebrow: 'Download',
    title: 'Ready to get started?',
    intro: 'Get the latest build straight from the project’s GitHub Releases.',
    required: 'Required',
    optional: 'Optional',
    app: {
      label: 'Windows app',
      name: 'AutoCatchPokemonPGSharp.exe',
      text: 'The latest release on GitHub. Settings, logs and bug reports are saved right next to the EXE.',
      stepsTitle: 'Quick start',
      steps: [
        'Download the latest EXE.',
        'Move it into its own writable folder, such as `D:\\AutoCatchPGSharp` — not inside a ZIP or Program Files.',
        'Run the app, click **Connect** and follow the four setup steps above.',
      ],
      button: 'Download for Windows',
      releaseNotes: 'Read the release notes',
    },
    extension: {
      label: 'Microsoft Edge extension',
      name: 'Discord Coord Collector v0.3.3',
      text: 'Collects Pokémon coordinates from Discord Web and hands them to the app one at a time.',
      note: 'The extension is only required for the Shundo from Discord Coordinates mode.',
      button: 'Download extension (.zip)',
      stepsTitle: 'Installing the extension',
      steps: [
        'Extract the downloaded ZIP file.',
        'Open `edge://extensions` and turn on **Developer mode**.',
        'Choose **Load unpacked** and select the extracted folder.',
      ],
    },
    smartscreen:
      'Windows SmartScreen may warn you because the app is unsigned. Only choose **More info → Run anyway** if the file came from the project’s official Releases page.',
  },

  faq: {
    eyebrow: 'FAQ',
    title: 'Frequently asked questions',
    intro: 'Can’t find what you need? Ask directly on the project’s Discord.',
    items: {
      key: {
        q: 'Does the application require a PGSharp key?',
        a: [
          'Not for quick catching. The **Quick Catch (No Key)** style performs the quick-catch gesture with Android touch control instead of PGSharp’s paid feature.',
          'You can also choose **Regular Catch**, which waits for the normal catch sequence.',
        ],
      },
      wifi: {
        q: 'Can the phone connect over Wi-Fi?',
        a: [
          'Yes. The first time, connect the phone by USB and click **Connect**; the app switches the device to Wi-Fi debugging and remembers it. Unplug the cable when the app confirms it is safe.',
          'After that, simply select the saved phone. If the connection drops, click **Refresh** or select the phone again. Both devices must be on the same Wi-Fi network.',
        ],
      },
      taps: {
        q: 'Why are taps misaligned?',
        a: [
          'The app scales coordinates to your screen size and DPI, but some phones can still be off. Open **Live view** to check the touch points and detection areas.',
          'If they really are off, open **Manual align** and adjust the relevant points for your screen. After changing resolution, DPI or the PGSharp layout, choose **Reset to default** and align again.',
        ],
      },
      balls: {
        q: 'What happens when I run out of Poké Balls?',
        a: [
          'Before reporting an empty bag, the app opens the ball picker in the bottom-right corner. If Great Balls or Ultra Balls are available, it loads them and keeps throwing.',
          'When the bag is truly empty, the app leaves the encounter, sends a Discord notification and pauses catching for 10 minutes while AutoWalk keeps collecting items. Catching then resumes automatically.',
        ],
      },
      devices: {
        q: 'Does the application support multiple devices?',
        a: [
          'It works across different phone models without forcing one resolution: it measures the interface scale, follows the real ball centre and can read the AutoWalk row from the Android view tree when icons differ.',
          'Connected phones are remembered, and when several are plugged in you choose which one to control. For cloned emulators there is an optional support profile of `1220 × 2712 @ 480 dpi`.',
        ],
      },
      discord: {
        q: 'Can I receive alerts through Discord?',
        a: [
          'Yes. Paste a Discord channel webhook URL into **Settings → Webhook URL**. Depending on the mode, you can get long-spawn-gap alerts, periodic reports, low battery, no balls, shiny screenshots and more.',
          'Leave the field empty if you do not need alerts.',
        ],
      },
      official: {
        q: 'Is this an official application?',
        a: [
          'No. This is an independent personal project. It is not an official product and is not affiliated with Niantic, The Pokémon Company or PGSharp.',
          'The source code is public for reference only and external code contributions are not accepted. Only download the EXE from the project’s official GitHub Releases page.',
        ],
      },
    },
  },

  community: {
    title: 'Join the Community',
    text: 'Ask setup questions, share bug reports and hear about new releases.',
    discord: 'Join Discord',
    kofi: 'Support on Ko-fi',
    source: 'View Source Code',
  },

  footer: {
    disclaimer:
      'This is an independent personal project. It is not an official product and is not affiliated with Niantic, The Pokémon Company or PGSharp. All related names and trademarks belong to their respective owners.',
    license:
      'The source code is publicly viewable for reference. Copying, modifying, redistributing or using it commercially requires the author’s written permission.',
    copyright: 'Copyright © 2026 Qpham. All Rights Reserved.',
    linksLabel: 'Links',
    licenseLink: 'License',
    releases: 'Releases',
  },
};
