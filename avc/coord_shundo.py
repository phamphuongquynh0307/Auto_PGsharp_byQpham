"""Independent Shundo mode whose teleport source is the Discord coordinate queue."""
from __future__ import annotations

from dataclasses import dataclass, replace

from .coord_source import CoordItem, CoordQueue
from .device import Device
from .layout import Layout
from .shundo import ShundoConfig, ShundoRoutine


@dataclass
class CoordShundoConfig(ShundoConfig):
    check_initial_nearby: bool = False
    require_confirmed_check: bool = True
    nearby_presence_frames: int = 3
    slot_foreground_bright_fraction: float = 0.008
    encounter_no_answer_attempts: int = 2
    bar_clear_timeout: float = 2.0

    # Authored from the supplied 422x934 / 426x931 screenshots and normalised to the app's
    # 1220x2712 base screen. The PGSharp shortcut menu is configured to stay expanded, so
    # teleport begins directly at its Teleport row without toggling the star/menu button.
    teleport_xy: tuple[int, int] = (390, 1150)
    teleport_input_xy: tuple[int, int] = (602, 1253)
    teleport_ok_xy: tuple[int, int] = (1005, 1675)

    dialog_open_wait: float = 0.45
    field_focus_wait: float = 0.35
    keyboard_hide_wait: float = 0.40
    coord_queue_poll: float = 1.0

    def scale_to(self, width: int, height: int, density: int | None = None,
                 *, scale: float | None = None) -> "CoordShundoConfig":
        parent = super().scale_to(width, height, density, scale=scale)
        base = self.base_config or self
        layout = Layout(width, height, density=density, scale=scale)
        return replace(
            parent,
            teleport_xy=layout.point(base.teleport_xy, "TL"),
            teleport_input_xy=layout.point(base.teleport_input_xy, "TL"),
            teleport_ok_xy=layout.point(base.teleport_ok_xy, "TL"),
        )


class CoordShundoRoutine(ShundoRoutine):
    def __init__(self, device: Device, coord_queue: CoordQueue,
                 config: CoordShundoConfig | None = None) -> None:
        super().__init__(device, config or CoordShundoConfig())
        self.coord_queue = coord_queue
        self.current_coord: CoordItem | None = None

    def _teleport_next(self, frame) -> str | None:
        cfg = self.config
        item = self.coord_queue.get(timeout=cfg.coord_queue_poll)
        if item is None:
            self.stats.last_event = "coord_idle"
            return "coord_idle"
        self.current_coord = item

        # The user's PGSharp shortcut menu stays expanded permanently.
        self.device.tap(*cfg.teleport_xy)
        self._interruptible_sleep(cfg.dialog_open_wait)
        self.device.tap(*cfg.teleport_input_xy)
        self._interruptible_sleep(cfg.field_focus_wait)
        self.device.clear_text(64)
        self._interruptible_sleep(0.10)
        self.device.input_coordinate(item.coordinate)
        self._interruptible_sleep(cfg.field_focus_wait)
        self.device.back()  # hide IME so OK returns to its calibrated position
        self._interruptible_sleep(cfg.keyboard_hide_wait)
        self.device.tap(*cfg.teleport_ok_xy)
        self._interruptible_sleep(min(0.75, cfg.teleport_wait))
        if self.stop_event.is_set():
            return "idle"
        return None
