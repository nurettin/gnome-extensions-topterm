import os
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, Gtk

from topterm import config
from topterm.config import Config
from topterm.window import TopTermWindow

APP_ID = "in.nurett.topterm"


class TopTermApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.cfg: Config = config.load(config.default_path())
        self.shell = os.environ.get("SHELL") or "/bin/bash"
        self.css_provider: Gtk.CssProvider | None = None
        self.window: TopTermWindow | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        toggle = Gio.SimpleAction.new("toggle", None)
        toggle.connect("activate", self._on_toggle)
        self.add_action(toggle)
        self._reload_css()

    def do_activate(self) -> None:
        if self.window is None:
            self.window = TopTermWindow(
                app=self,
                shell=self.shell,
                cwd=str(Path.home()),
            )
        self.window.present()

    def bg_rgba(self) -> Gdk.RGBA:
        rgba = Gdk.RGBA()
        if not rgba.parse(self.cfg.background):
            raise ValueError(f"invalid background color: {self.cfg.background!r}")
        rgba.alpha = 1.0 - (self.cfg.transparency / 100.0)
        return rgba

    def apply_appearance(self) -> None:
        self._reload_css()
        if self.window is not None:
            self.window.apply_appearance(self.bg_rgba(), self.cfg.font)

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
