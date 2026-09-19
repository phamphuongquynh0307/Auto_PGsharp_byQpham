/*
 * Bản dịch tiếng Việt.
 * - Giữ đúng cấu trúc khóa giống en.js (app.js kiểm tra và cảnh báo trong Console nếu thiếu khóa).
 * - **chữ đậm** và `mã` được hiển thị định dạng; không dùng HTML trong chuỗi.
 * - Nội dung phải bám README.vi.md / HUONG_DAN.md; không thêm số liệu hay tính năng không có trong repo.
 */
window.I18N = window.I18N || {};
window.I18N.vi = {
  meta: {
    title: 'Auto Catch Pokémon cho PGSharp – Tự động bắt Pokémon qua ADB',
    description:
      'Công cụ Windows điều khiển điện thoại Android qua ADB: tự động bắt Pokémon, Quick Catch không cần key, chấm shiny theo IV, nhận tọa độ từ Discord và quay PokéStop.',
    ogLocale: 'vi_VN',
    ogImage: 'og-image-vi.png',
    ogImageAlt: 'Auto Catch Pokémon cho PGSharp – công cụ Windows điều khiển điện thoại Android qua ADB',
    siteName: 'Auto Catch Pokémon cho PGSharp',
  },

  common: {
    skipToContent: 'Bỏ qua, tới nội dung chính',
    newTab: '(mở trong tab mới)',
    languageGroup: 'Chọn ngôn ngữ',
    languageChanged: 'Đã chuyển sang tiếng Việt',
    backToTop: 'Lên đầu trang',
    homeLabel: 'Auto Catch Pokémon cho PGSharp, về đầu trang',
    brandSub: 'cho PGSharp',
  },

  nav: {
    label: 'Điều hướng chính',
    features: 'Tính năng',
    modes: 'Chế độ',
    setup: 'Cách cài đặt',
    gallery: 'Hình ảnh',
    faq: 'Câu hỏi thường gặp',
    download: 'Tải bản mới nhất',
    openMenu: 'Mở menu',
    closeMenu: 'Đóng menu',
  },

  hero: {
    eyebrow: 'Dự án cá nhân · Mã nguồn công khai',
    titleLead: 'Tự động bắt Pokémon',
    titleAccent: 'trên PGSharp',
    description:
      'Công cụ Windows điều khiển điện thoại Android qua ADB, hỗ trợ bắt thường, Quick Catch không cần key, chấm shiny theo IV, nhận tọa độ từ Discord và tự động quay PokéStop.',
    ctaDownload: 'Tải ứng dụng cho Windows',
    ctaGithub: 'Xem trên GitHub',
    ctaGuide: 'Xem hướng dẫn',
    badgesLabel: 'Điểm nổi bật',
    badges: {
      windows: 'Windows',
      adb: 'Android + ADB',
      wifi: 'Kết nối Wi-Fi',
      quickCatch: 'Quick Catch không cần key',
      tests: '327+ bài kiểm thử tự động',
    },
    disclaimer: 'Không phải sản phẩm chính thức. Không liên kết với Niantic, The Pokémon Company hoặc PGSharp.',
    mockup: {
      label: 'Hình minh họa: ứng dụng trên Windows điều khiển điện thoại Android qua ADB không dây',
      caption: 'Hình minh họa giao diện',
      device: 'Thiết bị Android',
      connected: 'Đã kết nối Wi-Fi',
      modes: 'Chế độ',
      ivTarget: 'IV mục tiêu',
      ivAtk: 'Công',
      ivDef: 'Thủ',
      ivHp: 'HP',
      log: 'Nhật ký',
      run: 'Chạy',
      pause: 'Tạm dừng',
      stop: 'Dừng',
      link: 'ADB · Wi-Fi',
      nearby: 'Nearby',
    },
  },

  features: {
    eyebrow: 'Tính năng',
    title: 'Việc lặp lại, để ứng dụng lo',
    intro:
      'Ứng dụng đọc màn hình điện thoại theo thời gian thực, nhận diện giao diện PGSharp và điều khiển cảm ứng qua ADB.',
    items: {
      nearby: {
        title: 'Tự bắt từ Nearby',
        text: 'Tự động bắt Pokémon trong danh sách Nearby: mở encounter, ném bóng rồi quay lại bản đồ để chọn con tiếp theo.',
      },
      quickCatch: {
        title: 'Quick Catch không cần key',
        text: 'Điều khiển cảm ứng Android để ném bóng và thoát encounter thật nhanh, không cần key PGSharp trả phí.',
      },
      ballTracking: {
        title: 'Bám theo quả bóng',
        text: 'Tìm tâm quả bóng thật trên màn hình encounter rồi đặt điểm ném theo giao diện từng máy. Vẫn có thể căn tay khi cần.',
      },
      ivShiny: {
        title: 'Chấm shiny đúng IV',
        text: 'Nhập riêng IV Công/Thủ/HP từ 0 đến 15. Ứng dụng chỉ dừng khi shiny khớp đúng cả ba chỉ số.',
      },
      discordCoords: {
        title: 'Tọa độ từ Discord',
        text: 'Extension Edge gửi tọa độ Pokémon về ứng dụng. Bot teleport lần lượt và chỉ lấy tọa độ mới khi đã chấm xong.',
      },
      autoWalk: {
        title: 'AutoWalk và quay PokéStop',
        text: 'Giữ AutoWalk hoạt động và tự quay những PokéStop xanh nằm trong vùng quét quanh nhân vật.',
      },
      popups: {
        title: 'Tự né popup an toàn',
        text: 'Đóng cảnh báo thời tiết, tốc độ, level-up và màn hình PokéStop. Hộp thoại Android được đối chiếu đúng nút CANCEL/HỦY trước khi bấm.',
      },
      ballSwitch: {
        title: 'Tự đổi Great/Ultra Ball',
        text: 'Hết Poké Ball thì mở bảng chọn bóng và dùng loại còn lại. Chỉ báo hết bóng khi túi thật sự trống.',
      },
      webhook: {
        title: 'Cảnh báo qua Discord',
        text: 'Webhook báo spawn lâu, báo cáo định kỳ, pin yếu, hết bóng, gặp shiny và nhiều trạng thái khác.',
      },
      screens: {
        title: 'Thích nghi màn hình',
        text: 'Tự co giãn tọa độ theo kích thước và DPI của từng điện thoại Android, không cần ép đổi độ phân giải.',
      },
    },
  },

  modes: {
    eyebrow: 'Chế độ hoạt động',
    title: 'Bốn chế độ, một ứng dụng',
    intro: 'Mỗi chế độ cần một bố cục PGSharp riêng. Chọn chế độ, làm đúng checklist rồi bấm Chạy.',
    tabsLabel: 'Chọn chế độ hoạt động',
    prepareTitle: 'Cần chuẩn bị',
    viewImage: 'Phóng to ảnh hướng dẫn',
    items: {
      catch: {
        tab: 'Auto bắt Pokémon',
        summary: 'Tự động chọn Pokémon từ Nearby và thực hiện quy trình bắt.',
        points: [
          'Hai kiểu bắt: **Bắt thường** theo dõi kết quả và ném lại nếu Pokémon thoát ra; **Bắt nhanh** dùng Quick Catch không cần key.',
          'Giữ thanh Nearby bên phải hiện rõ, không để menu PGSharp che mất Pokémon đầu tiên.',
          'Lần đầu nên đặt **Giới hạn số con = 1** và quan sát trọn một lượt trước khi tăng.',
        ],
      },
      feed: {
        tab: 'Chấm shiny theo IV từ Feed',
        summary: 'Kiểm tra từng Pokémon và chỉ dừng khi shiny khớp chính xác ba chỉ số IV mục tiêu.',
        points: [
          'Bật **Block Non-Shiny** trong PGSharp để encounter chỉ mở khi gặp shiny.',
          'Mở Feed có biểu tượng RSS và giữ thanh Nearby có dấu `@` cùng hiện.',
          'Nếu chưa đọc chắc chắn IV, ứng dụng giữ encounter và tạm dừng thay vì bỏ nhầm.',
          'Ngắt Go Plus trước khi chạy, vì khi Go Plus còn kết nối PGSharp sẽ chặn teleport.',
        ],
      },
      coord: {
        tab: 'Shundo từ Discord Coord',
        summary: 'Nhận tọa độ từ extension Edge, teleport tuần tự và xử lý từng Pokémon.',
        points: [
          'Cài **Discord Coord Collector** cho Edge, đăng nhập Discord Web và Pokedex100 trong cùng profile.',
          'Mở sẵn menu shortcut PGSharp và căn ba điểm: dòng Teleport, ô Coordinates và nút OK.',
          'Mở ứng dụng, bấm **Chạy** trước, sau đó mới bấm **Bắt đầu** trên Collector.',
          'Bật Block Non-Shiny và ngắt Go Plus giống chế độ Feed.',
        ],
      },
      spin: {
        tab: 'Quay PokéStop khi đi đường',
        summary: 'Giữ AutoWalk và tự động quay những PokéStop phù hợp trong vùng quét.',
        points: [
          'Vòng quét mặc định có bán kính 450 px, giãn cách 2 giây giữa hai lần bấm.',
          'Chỉ bấm PokéStop xanh chưa quay trong vòng quét; stop tím đã quay được bỏ qua.',
          'Khi PGSharp hỏi **Stop AutoWalk?**, ứng dụng luôn chọn CANCEL và tự đóng màn PokéStop bằng dấu X.',
        ],
      },
    },
  },

  setup: {
    eyebrow: 'Cách cài đặt',
    title: 'Bắt đầu trong bốn bước',
    intro: 'Chỉ cần cáp USB ở lần kết nối đầu tiên. Những lần sau, ứng dụng tự kết nối lại qua Wi-Fi.',
    stepLabel: 'Bước {n}',
    steps: {
      usb: {
        title: 'Bật USB debugging trên điện thoại Android',
        text: 'Vào **Cài đặt → Giới thiệu điện thoại**, nhấn **Số hiệu bản dựng** 7 lần, rồi bật **Gỡ lỗi USB** trong Tùy chọn nhà phát triển.',
      },
      cable: {
        title: 'Kết nối điện thoại với máy tính lần đầu bằng USB',
        text: 'Dùng cáp truyền dữ liệu, mở ứng dụng, bấm **Kết nối** và cho phép gỡ lỗi khi Android hỏi.',
      },
      wifi: {
        title: 'Ứng dụng chuyển sang ADB qua Wi-Fi và ghi nhớ thiết bị',
        text: 'Rút cáp khi ứng dụng báo có thể rút an toàn. Những lần sau chỉ cần chọn điện thoại đã lưu.',
      },
      run: {
        title: 'Chọn chế độ rồi nhấn Chạy',
        text: 'Giữ Pokémon GO ở màn hình bản đồ, chọn chế độ và kiểu bắt, bấm **Chạy** rồi theo dõi trong khung nhật ký.',
      },
    },
    note: 'Điện thoại và máy tính cần kết nối cùng mạng Wi-Fi.',
    guideLink: 'Đọc hướng dẫn chi tiết cho từng chế độ',
    guideUrl: 'https://github.com/phamphuongquynh0307/Auto_PGsharp_byQpham/blob/master/HUONG_DAN.md',
  },

  gallery: {
    eyebrow: 'Hình ảnh',
    title: 'Hướng dẫn bằng hình',
    intro: 'Ảnh minh họa từng bước thiết lập, lấy từ bộ hướng dẫn có sẵn trong ứng dụng. Chọn một ảnh để phóng to.',
    regionLabel: 'Bộ ảnh hướng dẫn',
    open: 'Phóng to: {caption}',
    prev: 'Ảnh trước',
    next: 'Ảnh tiếp theo',
    scrollPrev: 'Cuộn về các ảnh trước',
    scrollNext: 'Cuộn tới các ảnh sau',
    close: 'Đóng',
    counter: 'Ảnh {current} / {total}',
    items: {
      appWindows: {
        caption: 'Tải ứng dụng từ Release',
        alt: 'Ba bước cài ứng dụng: tải AutoCatchPokemonPGSharp.exe từ trang Release, đặt vào thư mục riêng có quyền ghi và chọn Run anyway khi SmartScreen cảnh báo.',
      },
      usbDebug: {
        caption: 'Bật gỡ lỗi USB',
        alt: 'Ba màn hình Android: mở Giới thiệu điện thoại, nhấn Số hiệu bản dựng 7 lần và bật Gỡ lỗi USB trong Tùy chọn nhà phát triển.',
      },
      connectWifi: {
        caption: 'Kết nối qua Wi-Fi',
        alt: 'Cắm cáp USB và cho phép gỡ lỗi, chọn Wi-Fi (rút được cáp) rồi bấm Kết nối; nhật ký báo đã kết nối Wi-Fi và có thể rút cáp.',
      },
      testControl: {
        caption: 'Kiểm tra ADB và scrcpy',
        alt: 'Chọn đúng thiết bị, bấm Kiểm tra ADB/scrcpy, chờ đủ ba dòng thành công rồi mở cửa sổ Xem bot nhìn.',
      },
      catchLayout: {
        caption: 'Bố cục cho Auto bắt',
        alt: 'Màn hình PGSharp đúng cho Auto bắt: thanh Nearby bên phải, Pokémon đầu ở trên cùng, dấu @ không bị che và menu không che mục tiêu.',
      },
      shundoFeed: {
        caption: 'Thiết lập chấm shiny từ Feed',
        alt: 'Bật Block Non-Shiny, Encounter IV và Quick Load Map; mở Feed có biểu tượng RSS, giữ thanh Nearby @ cùng hiện và ngắt Virtual Go Plus.',
      },
      edgeExtension: {
        caption: 'Cài extension trên Edge',
        alt: 'Giải nén Discord Coord Collector, mở edge://extensions, bật Developer mode, chọn Load unpacked rồi mở popup Coord Collector.',
      },
      coordFlow: {
        caption: 'Luồng Discord Coord',
        alt: 'Căn ba điểm Teleport, Coordinates và OK; mở ứng dụng trước rồi bấm Bắt đầu trên Collector. Luồng: Collector, ứng dụng, teleport, chấm xong, lấy coord mới.',
      },
      spinPreview: {
        caption: 'Quay PokéStop khi đi đường',
        alt: 'Giữ AutoWalk trong shortcut và kiểm tra vòng quét: stop xanh sẽ được bấm, stop tím hoặc ngoài vòng bị bỏ qua; popup Stop AutoWalk luôn chọn CANCEL.',
      },
    },
  },

  requirements: {
    eyebrow: 'Yêu cầu hệ thống',
    title: 'Bạn cần chuẩn bị gì?',
    intro: 'Chuẩn bị đủ các mục dưới đây trước lần chạy đầu tiên.',
    items: {
      windows: { title: 'Máy tính Windows', text: 'Nơi chạy AutoCatchPokemonPGSharp.exe, đặt trong một thư mục riêng có quyền ghi.' },
      android: { title: 'Điện thoại Android', text: 'Giữ nguyên độ phân giải và DPI sau khi đã căn chỉnh.' },
      pgsharp: { title: 'Pokémon GO phiên bản PGSharp', text: 'Mở sẵn và vào hẳn màn hình bản đồ trước khi chạy.' },
      usbDebug: { title: 'USB debugging được bật', text: 'Bật trong Tùy chọn nhà phát triển của Android.' },
      wifi: { title: 'Hai thiết bị dùng cùng mạng Wi-Fi', text: 'Tắt VPN hoặc AP isolation nếu hai máy không nhìn thấy nhau.' },
      cable: { title: 'Cáp USB cho lần kết nối đầu tiên', text: 'Dùng cáp truyền dữ liệu; cáp chỉ sạc sẽ không dùng được.' },
    },
  },

  download: {
    eyebrow: 'Tải xuống',
    title: 'Sẵn sàng chạy thử?',
    intro: 'Tải bản mới nhất trực tiếp từ GitHub Releases của dự án.',
    required: 'Bắt buộc',
    optional: 'Tùy chọn',
    app: {
      label: 'Ứng dụng Windows',
      name: 'AutoCatchPokemonPGSharp.exe',
      text: 'Bản phát hành mới nhất trên GitHub. Cài đặt, nhật ký và báo cáo lỗi được lưu ngay cạnh file EXE.',
      stepsTitle: 'Bắt đầu nhanh',
      steps: [
        'Tải file EXE bản mới nhất.',
        'Chép vào một thư mục riêng có quyền ghi, ví dụ `D:\\AutoCatchPGSharp`; không để trong file ZIP hay Program Files.',
        'Mở ứng dụng, bấm **Kết nối** rồi làm theo bốn bước ở phần Cách cài đặt.',
      ],
      button: 'Tải cho Windows',
      releaseNotes: 'Xem ghi chú phát hành',
    },
    extension: {
      label: 'Extension cho Microsoft Edge',
      name: 'Discord Coord Collector v0.3.3',
      text: 'Thu thập tọa độ Pokémon từ Discord Web và gửi lần lượt về ứng dụng.',
      note: 'Extension chỉ cần thiết khi sử dụng chế độ Shundo từ Discord Coord.',
      button: 'Tải extension (.zip)',
      stepsTitle: 'Cách cài extension',
      steps: [
        'Giải nén file ZIP vừa tải.',
        'Mở `edge://extensions` và bật **Developer mode**.',
        'Chọn **Load unpacked** rồi trỏ tới thư mục vừa giải nén.',
      ],
    },
    smartscreen:
      'Windows SmartScreen có thể cảnh báo vì ứng dụng chưa được ký. Chỉ chọn **More info → Run anyway** khi file được tải từ trang Release chính thức của dự án.',
  },

  faq: {
    eyebrow: 'Câu hỏi thường gặp',
    title: 'Giải đáp nhanh',
    intro: 'Chưa thấy câu trả lời bạn cần? Hãy hỏi trực tiếp trên Discord của dự án.',
    items: {
      key: {
        q: 'Ứng dụng có cần key PGSharp không?',
        a: [
          'Không cần key để bắt nhanh. Kiểu **Bắt nhanh (không key)** điều khiển cảm ứng Android để thực hiện thao tác quick catch, thay cho tính năng trả phí của PGSharp.',
          'Bạn cũng có thể chọn **Bắt thường** để ứng dụng chờ toàn bộ hoạt ảnh bắt như bình thường.',
        ],
      },
      wifi: {
        q: 'Có thể kết nối điện thoại qua Wi-Fi không?',
        a: [
          'Có. Lần đầu, cắm điện thoại bằng cáp USB và bấm **Kết nối**; ứng dụng chuyển điện thoại sang gỡ lỗi qua Wi-Fi và ghi nhớ thiết bị. Rút cáp khi ứng dụng báo có thể rút an toàn.',
          'Những lần sau chỉ cần chọn điện thoại đã lưu. Nếu mất kết nối, bấm **Làm mới** hoặc chọn lại điện thoại. Hai thiết bị phải dùng cùng một mạng Wi-Fi.',
        ],
      },
      taps: {
        q: 'Vì sao ứng dụng chạm sai vị trí?',
        a: [
          'Ứng dụng tự co giãn tọa độ theo kích thước và DPI màn hình, nhưng một số máy vẫn có thể lệch. Hãy mở **Xem bot nhìn** để kiểm tra các điểm và khung nhận diện.',
          'Nếu lệch thật sự, mở **Căn chỉnh tay** và chỉnh đúng điểm tương ứng với màn hình. Sau khi đổi độ phân giải, DPI hoặc bố cục PGSharp, bấm **Đặt lại mặc định** rồi căn lại.',
        ],
      },
      balls: {
        q: 'Điều gì xảy ra khi hết Poké Ball?',
        a: [
          'Trước khi báo hết bóng, ứng dụng mở bảng chọn bóng ở góc dưới bên phải; còn Great Ball hoặc Ultra Ball thì chọn loại đó và ném tiếp.',
          'Khi túi thật sự hết bóng, ứng dụng thoát encounter, gửi cảnh báo Discord, tạm ngừng bắt trong 10 phút nhưng vẫn giữ AutoWalk để tìm thêm vật phẩm, sau đó tự bắt lại.',
        ],
      },
      devices: {
        q: 'Ứng dụng có hỗ trợ nhiều điện thoại không?',
        a: [
          'Có thể dùng với nhiều mẫu điện thoại khác nhau mà không cần cùng độ phân giải: ứng dụng tự đo tỉ lệ giao diện, bám theo tâm quả bóng thật và đọc hàng AutoWalk từ view Android khi icon khác phiên bản.',
          'Ứng dụng ghi nhớ các thiết bị đã kết nối; khi cắm nhiều máy cùng lúc, bạn chọn máy cần điều khiển. Nếu clone nhiều máy ảo, có thể dùng profile hỗ trợ `1220 × 2712 @ 480 dpi`.',
        ],
      },
      discord: {
        q: 'Có thể nhận cảnh báo qua Discord không?',
        a: [
          'Có. Dán URL webhook của kênh Discord vào **Cài đặt → Webhook URL**. Tùy chế độ, ứng dụng gửi thông báo spawn lâu, báo cáo định kỳ, pin yếu, hết bóng, ảnh shiny và nhiều trạng thái khác.',
          'Để trống ô này nếu bạn không cần cảnh báo.',
        ],
      },
      official: {
        q: 'Đây có phải ứng dụng chính thức không?',
        a: [
          'Không. Đây là dự án cá nhân, không phải sản phẩm chính thức và không liên kết với Niantic, The Pokémon Company hoặc PGSharp.',
          'Mã nguồn được công khai để tham khảo và repo không nhận đóng góp code từ bên ngoài. Chỉ tải file EXE từ trang Release chính thức của dự án trên GitHub.',
        ],
      },
    },
  },

  community: {
    title: 'Tham gia cộng đồng',
    text: 'Hỏi cách thiết lập, gửi báo cáo lỗi và nhận thông báo khi có bản cập nhật mới.',
    discord: 'Tham gia Discord',
    kofi: 'Ủng hộ trên Ko-fi',
    source: 'Xem mã nguồn',
  },

  footer: {
    disclaimer:
      'Đây là dự án cá nhân, không phải sản phẩm chính thức và không liên kết với Niantic, The Pokémon Company hoặc PGSharp. Tên và nhãn hiệu liên quan thuộc về chủ sở hữu tương ứng.',
    license:
      'Mã nguồn được công khai để tham khảo. Không được sao chép, chỉnh sửa, phát hành lại hoặc sử dụng thương mại khi chưa có sự cho phép bằng văn bản của tác giả.',
    copyright: 'Copyright © 2026 Qpham. All Rights Reserved.',
    linksLabel: 'Liên kết',
    licenseLink: 'Giấy phép',
    releases: 'Các bản phát hành',
  },
};
