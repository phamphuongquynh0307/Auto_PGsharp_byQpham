"""Auto Vision Clicker — desktop GUI.

A small tkinter control panel: pick the connected device, tune the catch settings,
and drive the catch routine with Play / Pause / Stop. The routine runs on a background
thread; log lines are marshalled back to the UI thread through a queue.
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from avc.catch import CatchConfig, CatchRoutine
from avc.device import Device


def _settings_path() -> str:
    """Store settings next to the exe (frozen) or the script (source)."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "settings.json")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Auto Vision Clicker — Bắt Pokemon")
        root.geometry("470x690")
        root.minsize(430, 640)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.routine: CatchRoutine | None = None
        self.device: Device | None = None
        self.worker: threading.Thread | None = None
        self.paused = False

        self._build_ui()
        self.load_settings()
        self.refresh_devices()
        self.root.after(100, self._drain_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI construction ------------------------------------------------------
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="Thiết bị:").pack(side="left")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(top, textvariable=self.device_var, state="readonly", width=22)
        self.device_combo.pack(side="left", padx=6)
        ttk.Button(top, text="Làm mới", command=self.refresh_devices).pack(side="left")

        # Settings
        cfg = ttk.LabelFrame(self.root, text="Cài đặt")
        cfg.pack(fill="x", **pad)
        self.slot_offset = self._spin(cfg, "Khoảng cách @ → ô đầu (px):", 0, 100, 1500, 770)
        self.throw_power = self._spin(cfg, "Lực ném (px, càng lớn càng mạnh):", 1, 200, 1400, 550)
        self.wait_enc = self._spin(cfg, "Chờ mở màn bắt tối đa (giây):", 2, 2, 15, 3.0, is_float=True)
        self.wait_catch = self._spin(cfg, "Chờ bắt xong tối đa (giây):", 3, 2, 20, 6.0, is_float=True)
        self.idle_aw = self._spin(cfg, "Trống mấy lần thì AutoWalk (0=tắt):", 4, 0, 20, 3)
        self.max_catches = self._spin(cfg, "Giới hạn số con (0=∞):", 5, 0, 9999, 0)
        self.dim_screen = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            cfg,
            text="Tắt sáng màn hình khi chạy (giảm nóng)",
            variable=self.dim_screen,
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        # Controls
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", **pad)
        self.play_btn = ttk.Button(controls, text="▶ Chạy", command=self.on_play)
        self.play_btn.pack(side="left", expand=True, fill="x", padx=3)
        self.pause_btn = ttk.Button(controls, text="⏸ Tạm dừng", command=self.on_pause, state="disabled")
        self.pause_btn.pack(side="left", expand=True, fill="x", padx=3)
        self.stop_btn = ttk.Button(controls, text="⏹ Dừng", command=self.on_stop, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=3)

        # Status + counter
        status = ttk.Frame(self.root)
        status.pack(fill="x", **pad)
        self.status_var = tk.StringVar(value="Sẵn sàng")
        ttk.Label(status, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.count_var = tk.StringVar(value="Đã ném: 0")
        ttk.Label(status, textvariable=self.count_var).pack(side="right")

        # Log
        logframe = ttk.LabelFrame(self.root, text="Nhật ký")
        logframe.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(logframe, height=10, wrap="word", state="disabled", font=("Consolas", 9))
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(logframe, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb.set)

    def _spin(self, parent, label, row, lo, hi, default, is_float=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=2)
        var = tk.DoubleVar(value=default) if is_float else tk.IntVar(value=default)
        inc = 0.5 if is_float else 1
        spin = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10, increment=inc)
        spin.grid(row=row, column=1, sticky="e", padx=6, pady=2)
        parent.columnconfigure(1, weight=1)
        return var

    # -- settings persistence -------------------------------------------------
    def load_settings(self) -> None:
        try:
            with open(_settings_path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        self.slot_offset.set(data.get("slot_offset", int(self.slot_offset.get())))
        self.throw_power.set(data.get("throw_power", int(self.throw_power.get())))
        # Encounters take ~2-3s to open; a stored wait below that makes the routine give up
        # mid-load and re-tap from scratch every cycle, so clamp old too-low values.
        self.wait_enc.set(max(2.0, float(data.get("wait_enc", self.wait_enc.get()))))
        self.wait_catch.set(max(2.0, float(data.get("wait_catch", self.wait_catch.get()))))
        self.idle_aw.set(data.get("idle_aw", int(self.idle_aw.get())))
        self.max_catches.set(data.get("max_catches", int(self.max_catches.get())))
        self.dim_screen.set(data.get("dim_screen", False))
        if data.get("device"):
            self.device_var.set(data["device"])

    def save_settings(self) -> None:
        data = {
            "slot_offset": int(self.slot_offset.get()),
            "throw_power": int(self.throw_power.get()),
            "wait_enc": float(self.wait_enc.get()),
            "wait_catch": float(self.wait_catch.get()),
            "idle_aw": int(self.idle_aw.get()),
            "max_catches": int(self.max_catches.get()),
            "dim_screen": bool(self.dim_screen.get()),
            "device": self.device_var.get(),
        }
        try:
            with open(_settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _on_close(self) -> None:
        if self.routine:
            self.routine.stop()
        # Best-effort: never leave the phone stuck at brightness 0 if closed mid-run.
        if self.device is not None:
            try:
                self.device.restore_dim()
            except Exception:  # noqa: BLE001
                pass
        self.save_settings()
        self.root.destroy()

    # -- device ---------------------------------------------------------------
    def refresh_devices(self) -> None:
        try:
            devices = Device.list_devices()
        except Exception as e:  # noqa: BLE001
            devices = []
            self._log(f"Lỗi liệt kê thiết bị: {e}")
        self.device_combo["values"] = devices
        if devices and not self.device_var.get():
            self.device_var.set(devices[0])
        if not devices:
            self.status_var.set("Không thấy thiết bị — cắm USB + bật gỡ lỗi")

    # -- run control ----------------------------------------------------------
    def on_play(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        serial = self.device_var.get()
        if not serial:
            self._log("Chưa chọn thiết bị.")
            return
        self.save_settings()
        cfg = CatchConfig(
            slot_offset_y=int(self.slot_offset.get()),
            throw_dy=-abs(int(self.throw_power.get())),
            encounter_timeout=max(2.0, float(self.wait_enc.get())),
            catch_timeout=max(2.0, float(self.wait_catch.get())),
            idle_before_autowalk=int(self.idle_aw.get()),
            max_catches=int(self.max_catches.get()),
        )
        try:
            self.device = Device(serial)
            self.routine = CatchRoutine(self.device, cfg)
        except Exception as e:  # noqa: BLE001
            self._log(f"Không khởi tạo được: {e}")
            return

        self.paused = False
        self.worker = threading.Thread(target=self._run_worker, daemon=True)
        self.worker.start()
        self.play_btn.config(state="disabled")
        self.pause_btn.config(state="normal", text="⏸ Tạm dừng")
        self.stop_btn.config(state="normal")
        self.status_var.set("Đang chạy…")
        self._log("Bắt đầu (bật stream realtime).")

    def _run_worker(self) -> None:
        def on_event(stats, threw):
            if stats.last_event == "autowalk":
                self.log_queue.put(f"→ Trống lâu, bấm AutoWalk đi kiếm spawn (lần {stats.autowalks})")
                return
            tag = "NÉM BÓNG" if threw else "(không có pokemon)"
            self.log_queue.put(f"chu kỳ {stats.cycles}: {tag} | tổng ném: {stats.throws}")
            self.log_queue.put(f"__count__{stats.throws}")

        dim = self.dim_screen.get()
        try:
            if dim:
                self.device.enable_dim()
                self.log_queue.put("Đã tắt sáng màn hình (game vẫn chạy nền).")
            self.device.start_stream()  # realtime H.264 capture
            self.routine.run(on_event=on_event)
            self.log_queue.put("__done__Hoàn tất.")
        except Exception as e:  # noqa: BLE001
            self.log_queue.put(f"__done__Lỗi: {e}")
        finally:
            self.device.stop_stream()
            if dim:
                self.device.restore_dim()

    def on_pause(self) -> None:
        if not self.routine:
            return
        if self.paused:
            self.routine.resume()
            self.paused = False
            self.pause_btn.config(text="⏸ Tạm dừng")
            self.status_var.set("Đang chạy…")
            self._log("Tiếp tục.")
        else:
            self.routine.pause()
            self.paused = True
            self.pause_btn.config(text="▶ Tiếp tục")
            self.status_var.set("Tạm dừng")
            self._log("Tạm dừng.")

    def on_stop(self) -> None:
        if self.routine:
            self.routine.stop()
            self.routine.resume()  # unblock a paused loop so it can see the stop
        self.status_var.set("Đang dừng…")

    def _finish(self, message: str) -> None:
        self.status_var.set("Sẵn sàng")
        self.play_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="⏸ Tạm dừng")
        self.stop_btn.config(state="disabled")
        self.paused = False
        self._log(message)

    # -- log pump -------------------------------------------------------------
    def _drain_log(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg.startswith("__count__"):
                    self.count_var.set(f"Đã ném: {msg[len('__count__'):]}")
                elif msg.startswith("__done__"):
                    self._finish(msg[len("__done__"):])
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _log(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
