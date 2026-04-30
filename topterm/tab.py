from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")

from gi.repository import Gdk, GLib, Gtk, Pango, Vte

ZOOM_STEP = 1.1
ZOOM_MIN = 0.5
ZOOM_MAX = 4.0


class TerminalTab(Gtk.Box):
    def __init__(
        self,
        shell: str,
        cwd: str,
        bg_rgba: Gdk.RGBA,
        font: str,
        zoom: float,
        on_zoom_change: Callable[[float], None],
        banner: str | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_zoom_change = on_zoom_change
        self.terminal = Vte.Terminal()
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_mouse_autohide(True)
        self.set_appearance(bg_rgba=bg_rgba, font=font)
        self.terminal.set_font_scale(zoom)
        self.append(self.terminal)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self.terminal.add_controller(scroll)

        middle_click = Gtk.GestureClick.new()
        middle_click.set_button(Gdk.BUTTON_MIDDLE)
        middle_click.connect("pressed", self._on_middle_click)
        self.terminal.add_controller(middle_click)

        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            cwd,
            [shell],
            [],
            GLib.SpawnFlags.SEARCH_PATH,
            None,
            None,
            -1,
            None,
            None,
            None,
        )

        if banner is not None:
            self.terminal.feed(banner.encode("utf-8"))

    def set_appearance(self, bg_rgba: Gdk.RGBA, font: str) -> None:
        self.terminal.set_color_background(bg_rgba)
        self.terminal.set_font(Pango.FontDescription.from_string(font))

    def set_zoom(self, zoom: float) -> None:
        self.terminal.set_font_scale(zoom)

    def _on_middle_click(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        self.terminal.paste_primary()

    def _on_scroll(self, controller: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        event = controller.get_current_event()
        if event is None:
            return False
        if not (event.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK):
            return False
        zoom = self.terminal.get_font_scale()
        zoom = zoom / ZOOM_STEP if dy > 0 else zoom * ZOOM_STEP
        self.on_zoom_change(max(ZOOM_MIN, min(ZOOM_MAX, zoom)))
        return True
