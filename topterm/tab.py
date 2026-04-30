import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")

from gi.repository import Gdk, GLib, Gtk, Pango, Vte

ZOOM_STEP = 1.1
ZOOM_MIN = 0.5
ZOOM_MAX = 4.0


class TerminalTab(Gtk.Box):
    def __init__(self, shell: str, cwd: str, bg_rgba: Gdk.RGBA, font: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.terminal = Vte.Terminal()
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_mouse_autohide(True)
        self.set_appearance(bg_rgba=bg_rgba, font=font)
        self.append(self.terminal)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self.terminal.add_controller(scroll)

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

    def set_appearance(self, bg_rgba: Gdk.RGBA, font: str) -> None:
        self.terminal.set_color_background(bg_rgba)
        self.terminal.set_font(Pango.FontDescription.from_string(font))

    def _on_scroll(self, controller: Gtk.EventControllerScroll, dx: float, dy: float) -> bool:
        event = controller.get_current_event()
        if event is None:
            return False
        if not (event.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK):
            return False
        scale = self.terminal.get_font_scale()
        scale = scale / ZOOM_STEP if dy > 0 else scale * ZOOM_STEP
        self.terminal.set_font_scale(max(ZOOM_MIN, min(ZOOM_MAX, scale)))
        return True
