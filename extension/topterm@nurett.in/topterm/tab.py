from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Vte", "3.91")

from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte

ZOOM_STEP = 1.1
ZOOM_MIN = 0.5
ZOOM_MAX = 4.0

# PCRE2 flags for vte_regex_new_for_search; matching what gnome-terminal /
# Ptyxis pass so multi-line scrollback content is searchable case-insensitively.
PCRE2_CASELESS = 0x00000008
PCRE2_MULTILINE = 0x00000400
SEARCH_FLAGS = PCRE2_CASELESS | PCRE2_MULTILINE

URL_REGEX = (
    r"(?:https?|ftp|file)://"
    r"[^\s<>\"'`{}|\\^\[\]]+"
)


class TerminalTab(Gtk.Box):
    def __init__(
        self,
        shell: str,
        cwd: str,
        bg_rgba: Gdk.RGBA,
        fg_rgba: Gdk.RGBA,
        palette: list[Gdk.RGBA],
        font: str,
        zoom: float,
        on_zoom_change: Callable[[float], None],
        on_exit: Callable[["TerminalTab"], None],
        banner: str | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_zoom_change = on_zoom_change
        self.on_exit = on_exit
        self.terminal = Vte.Terminal()
        self.terminal.set_hexpand(True)
        self.terminal.set_vexpand(True)
        self.terminal.set_scrollback_lines(10000)
        self.terminal.set_mouse_autohide(True)
        self.terminal.set_allow_hyperlink(True)
        self._add_url_matcher()
        self.set_appearance(
            bg_rgba=bg_rgba, fg_rgba=fg_rgba, palette=palette, font=font
        )
        self.terminal.set_font_scale(zoom)

        self.search_entry = Gtk.SearchEntry(hexpand=True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("next-match", lambda *_: self.terminal.search_find_next())
        self.search_entry.connect("previous-match", lambda *_: self.terminal.search_find_previous())
        self.search_entry.connect("activate", lambda *_: self.terminal.search_find_previous())
        self.search_entry.connect("stop-search", lambda *_: self.stop_search())

        self.search_bar = Gtk.SearchBar()
        self.search_bar.set_show_close_button(True)
        self.search_bar.set_child(self.search_entry)
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.connect("notify::search-mode-enabled", self._on_search_mode_changed)
        self.terminal.search_set_wrap_around(True)

        self.append(self.search_bar)
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

        # CAPTURE phase so a Ctrl+click on a URL is intercepted before VTE
        # starts a selection drag; the handler claims the gesture only when
        # a URL is actually under the pointer, otherwise the click falls
        # through to VTE's normal selection handling.
        link_click = Gtk.GestureClick.new()
        link_click.set_button(Gdk.BUTTON_PRIMARY)
        link_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        link_click.connect("pressed", self._on_link_click)
        self.terminal.add_controller(link_click)

        self.terminal.connect("child-exited", lambda *_: self.on_exit(self))

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

    def set_appearance(
        self,
        bg_rgba: Gdk.RGBA,
        fg_rgba: Gdk.RGBA,
        palette: list[Gdk.RGBA],
        font: str,
    ) -> None:
        self.terminal.set_colors(fg_rgba, bg_rgba, palette)
        self.terminal.set_font(Pango.FontDescription.from_string(font))

    def set_zoom(self, zoom: float) -> None:
        self.terminal.set_font_scale(zoom)

    def _on_middle_click(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        self.terminal.paste_primary()

    def _add_url_matcher(self) -> None:
        try:
            regex = Vte.Regex.new_for_match(URL_REGEX, -1, SEARCH_FLAGS)
        except GLib.Error:
            return
        tag = self.terminal.match_add_regex(regex, 0)
        self.terminal.match_set_cursor_name(tag, "pointer")

    def _on_link_click(
        self, gesture: Gtk.GestureClick, n_press: int, x: float, y: float
    ) -> None:
        event = gesture.get_current_event()
        if event is None:
            return
        if not (event.get_modifier_state() & Gdk.ModifierType.CONTROL_MASK):
            return
        # OSC 8 hyperlinks first; they carry an explicit URI even when the
        # visible text doesn't look like a URL.
        uri = self.terminal.check_hyperlink_at(x, y)
        if uri is None:
            match, _tag = self.terminal.check_match_at(x, y)
            uri = match
        if uri is None:
            return
        Gio.AppInfo.launch_default_for_uri(uri, None)
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

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

    def start_search(self) -> None:
        self.search_bar.set_search_mode(True)
        self.search_entry.grab_focus()

    def stop_search(self) -> None:
        self.search_bar.set_search_mode(False)

    def _on_search_mode_changed(self, *_: object) -> None:
        if self.search_bar.get_search_mode():
            return
        # Closing path (Esc, close button, or programmatic): wipe highlights
        # and selection, hand focus back so typing goes to the shell again.
        self.terminal.search_set_regex(None, 0)
        self.terminal.unselect_all()
        self.terminal.grab_focus()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        text = entry.get_text()
        if not text:
            self.terminal.search_set_regex(None, 0)
            return
        pattern = GLib.Regex.escape_string(text, -1)
        try:
            regex = Vte.Regex.new_for_search(pattern, -1, SEARCH_FLAGS)
        except GLib.Error:
            return
        self.terminal.search_set_regex(regex, 0)
        # Search backwards first so the most recent match (likely on-screen)
        # gets highlighted instead of jumping to the oldest scrollback hit.
        self.terminal.search_find_previous()
