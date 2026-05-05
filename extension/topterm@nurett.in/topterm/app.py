import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, Gtk

from topterm import config, ptyxis
from topterm.config import Config
from topterm.ptyxis import PtyxisColors, PtyxisTheme
from topterm.window import TopTermWindow

APP_ID = "in.nurett.topterm"

# Adwaita view backgrounds; chosen so a default-config dropdown matches
# Files/Text Editor when the user toggles light/dark.
THEME_BG_LIGHT = "#ffffff"
THEME_BG_DARK = "#1e1e1e"
THEME_FG_LIGHT = "#1e1e1e"
THEME_FG_DARK = "#ffffff"

# Tango: neutral 16-color fallback when Ptyxis isn't available, so red/green/
# blue still read sensibly on either light or dark Adwaita.
TANGO_PALETTE = (
    "#2e3436", "#cc0000", "#4e9a06", "#c4a000",
    "#3465a4", "#75507b", "#06989a", "#d3d7cf",
    "#555753", "#ef2929", "#8ae234", "#fce94f",
    "#729fcf", "#ad7fa8", "#34e2e2", "#eeeeec",
)


class TopTermApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        cfg_path = config.default_path()
        self.cfg: Config = config.load(cfg_path)
        self.shell = os.environ.get("SHELL") or "/bin/bash"
        self.css_provider: Gtk.CssProvider | None = None
        self.window: TopTermWindow | None = None
        self.style_manager = Adw.StyleManager.get_default()
        self.style_manager.connect("notify::dark", lambda *_: self.apply_appearance())
        self.ptyxis_theme: PtyxisTheme | None = ptyxis.detect()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        toggle = Gio.SimpleAction.new("toggle", None)
        toggle.connect("activate", self._on_toggle)
        self.add_action(toggle)
        self._reload_css()

    def do_activate(self) -> None:
        if self.window is None:
            show_banner = not self.cfg.banner_shown
            self.window = TopTermWindow(
                app=self,
                shell=self.shell,
                cwd=str(Path.home()),
                first_run=show_banner,
            )
            if show_banner:
                self.cfg.banner_shown = True
                self.save_config()
        self.window.present()

    def bg_rgba(self) -> Gdk.RGBA:
        if self.cfg.follow_theme:
            ptyxis_colors = self._ptyxis_colors()
            if ptyxis_colors is not None:
                spec = ptyxis_colors.bg
            else:
                spec = THEME_BG_DARK if self.style_manager.get_dark() else THEME_BG_LIGHT
        else:
            spec = self.cfg.background
        rgba = Gdk.RGBA()
        if not rgba.parse(spec):
            raise ValueError(f"invalid background color: {spec!r}")
        rgba.alpha = 1.0 - (self.cfg.transparency / 100.0)
        return rgba

    def fg_rgba(self) -> Gdk.RGBA:
        if self.cfg.follow_theme:
            ptyxis_colors = self._ptyxis_colors()
            if ptyxis_colors is not None:
                spec = ptyxis_colors.fg
            else:
                spec = THEME_FG_DARK if self.style_manager.get_dark() else THEME_FG_LIGHT
        else:
            # Pick fg by bg luminance so manual dark bg gets light text and vice versa.
            spec = THEME_FG_DARK if _is_dark_color(self.cfg.background) else THEME_FG_LIGHT
        rgba = Gdk.RGBA()
        rgba.parse(spec)
        return rgba

    def palette_rgba(self) -> list[Gdk.RGBA]:
        if self.cfg.follow_theme:
            ptyxis_colors = self._ptyxis_colors()
            specs = ptyxis_colors.palette if ptyxis_colors is not None else TANGO_PALETTE
        else:
            specs = TANGO_PALETTE
        out: list[Gdk.RGBA] = []
        for hex_ in specs:
            rgba = Gdk.RGBA()
            rgba.parse(hex_)
            out.append(rgba)
        return out

    def effective_font(self) -> str:
        if self.cfg.follow_theme and self.ptyxis_theme is not None:
            font = self.ptyxis_theme.font
            if font:
                return font
        return self.cfg.font

    def _ptyxis_colors(self) -> PtyxisColors | None:
        if self.ptyxis_theme is None:
            return None
        return self.ptyxis_theme.dark if self.style_manager.get_dark() else self.ptyxis_theme.light

    def apply_appearance(self) -> None:
        self._reload_css()
        if self.window is not None:
            self.window.apply_appearance(
                bg_rgba=self.bg_rgba(),
                fg_rgba=self.fg_rgba(),
                palette=self.palette_rgba(),
                font=self.effective_font(),
            )

    def apply_shortcuts(self) -> None:
        if self.window is not None:
            self.window.apply_shortcuts(self.cfg.shortcuts)

    def save_config(self) -> None:
        config.save(self.cfg)

    def _reload_css(self) -> None:
        bg = self.bg_rgba().to_string()
        # Strip background paints down through the toolbar so Vte's alpha
        # composites against the wallpaper. Top bar gets the rgba so the
        # chrome stays uniform.
        css = (
            "window.background, toolbarview, .toolbar-view {"
            "  background: transparent;"
            "}"
            f"toolbarview > .top-bar, .top-bar {{ background-color: {bg}; }}"
        )
        if self.css_provider is None:
            self.css_provider = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        self.css_provider.load_from_string(css)

    def _on_toggle(self, *_: object) -> None:
        if self.window is None:
            self.activate()
            return
        if self.window.get_visible():
            self.window.set_visible(False)
        else:
            self.window.present()


def _is_dark_color(spec: str) -> bool:
    rgba = Gdk.RGBA()
    if not rgba.parse(spec):
        return True
    luminance = 0.299 * rgba.red + 0.587 * rgba.green + 0.114 * rgba.blue
    return luminance < 0.5
