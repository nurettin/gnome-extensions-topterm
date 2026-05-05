import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Vte", "3.91")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, Gtk

from topterm.config import Shortcuts
from topterm.tab import TerminalTab, ZOOM_MAX, ZOOM_MIN, ZOOM_STEP

COVERAGE_STEP = 5
COVERAGE_MIN = 10
COVERAGE_MAX = 100
TRANSPARENCY_STEP = 5
TRANSPARENCY_MIN = 0
TRANSPARENCY_MAX = 100

ADJUST_BINDINGS: tuple[tuple[str, str], ...] = (
    ("<Primary><Shift>Down", "win.taller"),
    ("<Primary><Shift>Up", "win.shorter"),
    ("<Primary><Shift>t", "win.more-transparent"),
    ("<Primary><Shift>o", "win.more-opaque"),
    ("<Primary>plus", "win.zoom-in"),
    ("<Primary>equal", "win.zoom-in"),
    ("<Primary>KP_Add", "win.zoom-in"),
    ("<Primary>minus", "win.zoom-out"),
    ("<Primary>KP_Subtract", "win.zoom-out"),
)

TAB_SELECT_BINDINGS: tuple[tuple[str, str], ...] = tuple(
    (f"<Alt>{i % 10}", f"win.select-tab-{i}") for i in range(1, 11)
)

WELCOME_BANNER = (
    "# Welcome to topterm — opinionated dropdown terminal for GNOME Wayland\r\n"
    "#\r\n"
    "# Shortcuts:\r\n"
    "#   F1                   toggle (gsettings org.gnome.shell.extensions.topterm toggle)\r\n"
    "#   Ctrl+T / Ctrl+W      new / close tab\r\n"
    "#   F2                   rename current tab\r\n"
    "#   Ctrl+F               find in scrollback (Esc to close)\r\n"
    "#   Alt+1..9, Alt+0      jump to tab 1..9, 10\r\n"
    "#   Ctrl+Shift+Up/Down   shorter / taller (5%)\r\n"
    "#   Ctrl+Shift+T / O     more transparent / more opaque (5%)\r\n"
    "#   Ctrl++ / Ctrl+-      zoom in / out  (also Ctrl+Scroll)\r\n"
    "#   Middle-click         paste primary selection\r\n"
    "#\r\n"
    "# Config: ~/.config/topterm/config.ini\r\n"
    "#\r\n"
)


class TopTermWindow(Adw.ApplicationWindow):
    def __init__(self, app, shell: str, cwd: str, first_run: bool) -> None:
        super().__init__(application=app)
        self.app = app
        self.shell = shell
        self.cwd = cwd
        self.set_title("topterm")
        self.set_default_size(1200, 400)

        self.tab_view = Adw.TabView()
        self.tab_view.connect("close-page", self._on_close_page)
        self.tab_view.connect("page-detached", self._on_page_detached)

        tab_bar = Adw.TabBar(view=self.tab_view, autohide=False, expand_tabs=False)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(tab_bar)
        toolbar.set_content(self.tab_view)
        self.set_content(toolbar)

        self._install_actions()
        self.shortcut_controller: Gtk.ShortcutController | None = None
        self.apply_shortcuts(self.app.cfg.shortcuts)

        self.add_tab(banner=WELCOME_BANNER if first_run else None)

        self.connect("close-request", self._on_close_request)
        self.connect("notify::is-active", self._on_active_changed)

    def _install_actions(self) -> None:
        actions = {
            "new-tab": lambda *_: self.add_tab(),
            "close-tab": lambda *_: self._close_current_tab(),
            "rename-tab": lambda *_: self.rename_current_tab(),
            "find": lambda *_: self._start_search_in_current_tab(),
            "taller": lambda *_: self._adjust_coverage(+COVERAGE_STEP),
            "shorter": lambda *_: self._adjust_coverage(-COVERAGE_STEP),
            "more-transparent": lambda *_: self._adjust_transparency(+TRANSPARENCY_STEP),
            "more-opaque": lambda *_: self._adjust_transparency(-TRANSPARENCY_STEP),
            "zoom-in": lambda *_: self._adjust_zoom(ZOOM_STEP),
            "zoom-out": lambda *_: self._adjust_zoom(1.0 / ZOOM_STEP),
        }
        for i in range(1, 11):
            actions[f"select-tab-{i}"] = (
                lambda *_, idx=i - 1: self._select_tab(idx)
            )
        for name, callback in actions.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    # ---- tabs -------------------------------------------------------------

    def add_tab(self, banner: str | None = None) -> Adw.TabPage:
        tab = TerminalTab(
            shell=self.shell,
            cwd=self.cwd,
            bg_rgba=self.app.bg_rgba(),
            fg_rgba=self.app.fg_rgba(),
            palette=self.app.palette_rgba(),
            font=self.app.effective_font(),
            zoom=self.app.cfg.zoom,
            on_zoom_change=self._on_zoom_change,
            on_exit=self._on_tab_exit,
            banner=banner,
        )
        page = self.tab_view.append(tab)
        page.set_title(f"Terminal {self.tab_view.get_n_pages()}")
        self.tab_view.set_selected_page(page)
        return page

    def _on_tab_exit(self, tab: TerminalTab) -> None:
        page = self.tab_view.get_page(tab)
        if page is not None:
            self.tab_view.close_page(page)

    def rename_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is None:
            return
        dialog = Adw.AlertDialog.new("Rename tab", None)
        entry = Gtk.Entry(text=page.get_title())
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Rename")
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response == "ok":
                page.set_title(entry.get_text() or page.get_title())

        dialog.connect("response", on_response)
        dialog.present(self)

    # ---- live re-apply ----------------------------------------------------

    def apply_appearance(
        self,
        bg_rgba: Gdk.RGBA,
        fg_rgba: Gdk.RGBA,
        palette: list[Gdk.RGBA],
        font: str,
    ) -> None:
        n = self.tab_view.get_n_pages()
        for i in range(n):
            page = self.tab_view.get_nth_page(i)
            tab = page.get_child()
            if isinstance(tab, TerminalTab):
                tab.set_appearance(
                    bg_rgba=bg_rgba, fg_rgba=fg_rgba, palette=palette, font=font
                )

    def apply_zoom(self, zoom: float) -> None:
        n = self.tab_view.get_n_pages()
        for i in range(n):
            page = self.tab_view.get_nth_page(i)
            tab = page.get_child()
            if isinstance(tab, TerminalTab):
                tab.set_zoom(zoom)

    def _on_zoom_change(self, zoom: float) -> None:
        if zoom == self.app.cfg.zoom:
            return
        self.app.cfg.zoom = zoom
        self.app.save_config()
        self.apply_zoom(zoom)

    def apply_shortcuts(self, shortcuts: Shortcuts) -> None:
        if self.shortcut_controller is not None:
            self.remove_controller(self.shortcut_controller)
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        bindings = (
            (shortcuts.new_tab, "win.new-tab"),
            (shortcuts.close_tab, "win.close-tab"),
            (shortcuts.rename_tab, "win.rename-tab"),
            (shortcuts.find, "win.find"),
            *ADJUST_BINDINGS,
            *TAB_SELECT_BINDINGS,
        )
        for accel, action_name in bindings:
            controller.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(accel),
                    Gtk.NamedAction.new(action_name),
                )
            )
        self.add_controller(controller)
        self.shortcut_controller = controller

    # ---- live adjustments -------------------------------------------------

    def _adjust_coverage(self, delta: int) -> None:
        new = max(COVERAGE_MIN, min(COVERAGE_MAX, self.app.cfg.coverage + delta))
        if new == self.app.cfg.coverage:
            return
        self.app.cfg.coverage = new
        self.app.save_config()
        # Hide+show so the extension's map handler repositions with the new
        # coverage. There's no public API to ask Mutter to re-run our placement
        # without unmapping.
        self.set_visible(False)
        self.present()

    def _adjust_zoom(self, factor: float) -> None:
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.app.cfg.zoom * factor))
        self._on_zoom_change(zoom)

    def _adjust_transparency(self, delta: int) -> None:
        new = max(
            TRANSPARENCY_MIN,
            min(TRANSPARENCY_MAX, self.app.cfg.transparency + delta),
        )
        if new == self.app.cfg.transparency:
            return
        self.app.cfg.transparency = new
        self.app.save_config()
        self.app.apply_appearance()

    # ---- action handlers --------------------------------------------------

    def _close_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is not None:
            self.tab_view.close_page(page)

    def _start_search_in_current_tab(self) -> None:
        page = self.tab_view.get_selected_page()
        if page is None:
            return
        tab = page.get_child()
        if isinstance(tab, TerminalTab):
            tab.start_search()

    def _select_tab(self, idx: int) -> None:
        if 0 <= idx < self.tab_view.get_n_pages():
            self.tab_view.set_selected_page(self.tab_view.get_nth_page(idx))

    # ---- window lifecycle -------------------------------------------------

    def _on_close_page(self, view: Adw.TabView, page: Adw.TabPage) -> bool:
        view.close_page_finish(page, True)
        return True

    def _on_page_detached(self, view: Adw.TabView, page: Adw.TabPage, pos: int) -> None:
        if view.get_n_pages() == 0:
            self.get_application().quit()

    def _on_close_request(self, *_: object) -> bool:
        self.set_visible(False)
        return True

    def _on_active_changed(self, *_: object) -> None:
        if self.get_visible() and not self.is_active():
            self.set_visible(False)
