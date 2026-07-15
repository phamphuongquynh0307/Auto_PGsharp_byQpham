"""Auto Vision Clicker — entry point.

Right now this is a minimal, working skeleton that proves the full round-trip:
  capture the phone screen -> find a template image -> tap where it was found.

Features (what to do on a match, sequences, timing, multiple templates, ...) will be
layered on top of this core once decided.

Usage examples:
  python main.py devices
  python main.py shot                       # save a screenshot to screenshot.png
  python main.py watch templates/button.png # loop: find button.png, tap it, repeat
"""
from __future__ import annotations

import argparse
import sys
import time

import cv2

from avc.catch import CatchConfig, CatchRoutine
from avc.device import Device
from avc.vision import find, load_template

# Windows consoles default to cp1252 and choke on Vietnamese output; force UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def pick_device(serial: str | None) -> Device:
    devices = Device.list_devices()
    if not devices:
        print("Không thấy thiết bị nào. Cắm điện thoại + bật USB debugging, thử: adb devices")
        sys.exit(1)
    if serial and serial not in devices:
        print(f"Không thấy thiết bị {serial}. Có: {devices}")
        sys.exit(1)
    dev = Device(serial or devices[0])
    return dev


def cmd_devices(_args) -> None:
    devices = Device.list_devices()
    print("Thiết bị đang kết nối:", devices or "(không có)")
    for s in devices:
        d = Device(s)
        try:
            print(f"  {s}  {d.screen_size()[0]}x{d.screen_size()[1]}")
        except Exception as e:  # noqa: BLE001
            print(f"  {s}  (lỗi đọc kích thước: {e})")


def cmd_shot(args) -> None:
    dev = pick_device(args.serial)
    img = dev.screenshot()
    cv2.imwrite(args.out, img)
    print(f"Đã lưu ảnh màn hình: {args.out}  {img.shape[1]}x{img.shape[0]}")


def cmd_watch(args) -> None:
    dev = pick_device(args.serial)
    template = load_template(args.template)
    scales = tuple(float(s) for s in args.scales.split(",")) if args.scales else (1.0,)
    print(
        f"Đang theo dõi {args.template} | ngưỡng={args.threshold} | "
        f"chu kỳ={args.interval}s | {'CHỈ báo' if args.dry_run else 'sẽ BẤM'} (Ctrl+C để dừng)"
    )
    fired = 0
    try:
        while True:
            frame = dev.screenshot()
            matches = find(frame, template, threshold=args.threshold, scales=scales, max_matches=args.max)
            if matches:
                best = matches[0]
                cx, cy = best.center
                print(f"  khớp score={best.score:.2f} tại ({cx},{cy}) [{len(matches)} vị trí]")
                if not args.dry_run:
                    dev.tap(cx, cy)
                    fired += 1
                if args.once:
                    break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nDừng. Đã bấm {fired} lần.")


def cmd_catch(args) -> None:
    dev = pick_device(args.serial)
    cfg = CatchConfig(
        nearby_slot=(args.slot_x, args.slot_y),
        after_double_tap=args.wait_encounter,
        after_throw=args.wait_catch,
        max_catches=args.max,
    )
    routine = CatchRoutine(dev, cfg)
    print(
        f"Bắt Pokemon | ô nearby=({cfg.nearby_slot[0]},{cfg.nearby_slot[1]}) | "
        f"{'giới hạn ' + str(args.max) if args.max else 'không giới hạn'} lần | Ctrl+C để dừng"
    )

    def report(stats, threw):
        tag = "NÉM BÓNG" if threw else "(không có pokemon, bỏ qua)"
        print(f"  chu kỳ {stats.cycles}: {tag}  | tổng ném: {stats.throws}")

    try:
        routine.run(on_event=report)
        print(f"Xong. Tổng ném bóng: {routine.stats.throws}")
    except KeyboardInterrupt:
        print(f"\nDừng. Tổng ném bóng: {routine.stats.throws}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Auto Vision Clicker (PC + ADB)")
    p.add_argument("--serial", help="ADB serial của thiết bị (mặc định: cái đầu tiên)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="Liệt kê thiết bị").set_defaults(func=cmd_devices)

    sp_shot = sub.add_parser("shot", help="Chụp 1 ảnh màn hình")
    sp_shot.add_argument("--out", default="screenshot.png")
    sp_shot.set_defaults(func=cmd_shot)

    sp_watch = sub.add_parser("watch", help="Lặp: tìm template rồi bấm")
    sp_watch.add_argument("template", help="Đường dẫn ảnh mẫu (.png)")
    sp_watch.add_argument("--threshold", type=float, default=0.8)
    sp_watch.add_argument("--interval", type=float, default=0.5, help="Giây giữa mỗi lần quét")
    sp_watch.add_argument("--scales", default="1.0", help="Danh sách scale, vd: 0.8,0.9,1.0,1.1")
    sp_watch.add_argument("--max", type=int, default=10, help="Số vị trí khớp tối đa mỗi khung")
    sp_watch.add_argument("--once", action="store_true", help="Bấm 1 lần rồi thoát")
    sp_watch.add_argument("--dry-run", action="store_true", help="Chỉ báo vị trí, không bấm")
    sp_watch.set_defaults(func=cmd_watch)

    sp_catch = sub.add_parser("catch", help="Bắt Pokemon: double-tap nearby -> vuốt bóng")
    sp_catch.add_argument("--slot-x", type=int, default=940, help="X của ô nearby đầu tiên")
    sp_catch.add_argument("--slot-y", type=int, default=205, help="Y của ô nearby đầu tiên")
    sp_catch.add_argument("--wait-encounter", type=float, default=2.0, help="Chờ mở màn bắt (giây)")
    sp_catch.add_argument("--wait-catch", type=float, default=4.0, help="Chờ animation bắt (giây)")
    sp_catch.add_argument("--max", type=int, default=0, help="Số lần bắt tối đa (0 = vô hạn)")
    sp_catch.set_defaults(func=cmd_catch)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
