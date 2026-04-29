import configparser
from dataclasses import dataclass, field
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, Gtk, Pango


@dataclass
class Shortcuts:
    new_tab: str
    close_tab: str
    rename_tab: str


@dataclass
class Config:
    path: Path
    coverage: int  # height % of monitor (1..100)
    background: str  # CSS color string, e.g. "#1e1e1e"
    transparency: int  # 0..100 (% transparent; 0 = opaque)
    font: str  # Pango font description, e.g. "Monospace 11"
    shortcuts: Shortcuts


_DEFAULTS_UI = {
    "coverage": "50",
    "background": "#1e1e1e",
    "transparency": "0",
    "font": "Monospace 11",
}
_DEFAULTS_SHORTCUTS = {
    "new_tab": "<Primary>t",
    "close_tab": "<Primary>w",
    "rename_tab": "F2",
}


def default_path() -> Path:
    return Path.home() / ".config" / "qterm" / "config.ini"


def load(path: Path) -> Config:
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path)

    ui = parser["ui"] if parser.has_section("ui") else {}
    sc = parser["shortcuts"] if parser.has_section("shortcuts") else {}

    coverage = _parse_int_in_range(
        "coverage", ui.get("coverage", _DEFAULTS_UI["coverage"]), 1, 100
    )
    background = ui.get("background", _DEFAULTS_UI["background"])
    _validate_color(background)
    transparency = _parse_int_in_range(
        "transparency", ui.get("transparency", _DEFAULTS_UI["transparency"]), 0, 100
    )
    font = ui.get("font", _DEFAULTS_UI["font"])
    _validate_font(font)

    shortcuts = Shortcuts(
        new_tab=_validate_accel(
            "new_tab", sc.get("new_tab", _DEFAULTS_SHORTCUTS["new_tab"])
        ),
        close_tab=_validate_accel(
            "close_tab", sc.get("close_tab", _DEFAULTS_SHORTCUTS["close_tab"])
        ),
        rename_tab=_validate_accel(
            "rename_tab", sc.get("rename_tab", _DEFAULTS_SHORTCUTS["rename_tab"])
        ),
    )

    cfg = Config(
        path=path,
        coverage=coverage,
        background=background,
        transparency=transparency,
        font=font,
        shortcuts=shortcuts,
    )

    if not path.exists():
        save(cfg)

    return cfg


def save(cfg: Config) -> None:
    parser = configparser.ConfigParser()
    parser["ui"] = {
        "coverage": str(cfg.coverage),
        "background": cfg.background,
        "transparency": str(cfg.transparency),
        "font": cfg.font,
    }
    parser["shortcuts"] = {
        "new_tab": cfg.shortcuts.new_tab,
        "close_tab": cfg.shortcuts.close_tab,
        "rename_tab": cfg.shortcuts.rename_tab,
    }
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    with cfg.path.open("w") as f:
        parser.write(f)


def _parse_int_in_range(name: str, value: str, lo: int, hi: int) -> int:
    n = int(value)
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be {lo}..{hi}, got {n}")
    return n


def _validate_color(value: str) -> None:
    rgba = Gdk.RGBA()
    if not rgba.parse(value):
        raise ValueError(f"invalid color: {value!r}")


def _validate_font(value: str) -> None:
    desc = Pango.FontDescription.from_string(value)
    if desc.get_family() is None or desc.get_size() == 0:
        raise ValueError(f"invalid font: {value!r}")


def _validate_accel(name: str, value: str) -> str:
    if Gtk.ShortcutTrigger.parse_string(value) is None:
        raise ValueError(f"invalid accelerator for {name}: {value!r}")
    return value
