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
    find: str


@dataclass
class Config:
    path: Path
    coverage: int  # height % of monitor (1..100)
    follow_theme: bool  # match GNOME light/dark theme; ignores `background` when true
    background: str  # CSS color string, e.g. "#1e1e1e" (used when follow_theme=false)
    transparency: int  # 0..100 (% transparent; 0 = opaque)
    font: str  # Pango font description, e.g. "Monospace 11"
    zoom: float  # vte font scale (0.5..4.0); 1.0 = no zoom
    banner_shown: bool  # welcome banner shown once
    shortcuts: Shortcuts


_DEFAULTS_UI = {
    "coverage": "50",
    "follow_theme": "true",
    "background": "#1e1e1e",
    "transparency": "0",
    "font": "Monospace 12",
    "zoom": "1.0",
    "banner_shown": "false",
}
_DEFAULTS_SHORTCUTS = {
    "new_tab": "<Primary>t",
    "close_tab": "<Primary>w",
    "rename_tab": "F2",
    "find": "<Primary>f",
}


def default_path() -> Path:
    return Path.home() / ".config" / "topterm" / "config.ini"


def load(path: Path) -> Config:
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(path)

    ui = parser["ui"] if parser.has_section("ui") else {}
    sc = parser["shortcuts"] if parser.has_section("shortcuts") else {}

    coverage = _parse_int_in_range(
        "coverage", ui.get("coverage", _DEFAULTS_UI["coverage"]), 1, 100
    )
    follow_theme = _parse_bool(
        "follow_theme", ui.get("follow_theme", _DEFAULTS_UI["follow_theme"])
    )
    background = ui.get("background", _DEFAULTS_UI["background"])
    _validate_color(background)
    transparency = _parse_int_in_range(
        "transparency", ui.get("transparency", _DEFAULTS_UI["transparency"]), 0, 100
    )
    font = ui.get("font", _DEFAULTS_UI["font"])
    _validate_font(font)
    zoom = _parse_float_in_range(
        "zoom", ui.get("zoom", _DEFAULTS_UI["zoom"]), 0.5, 4.0
    )
    banner_shown = _parse_bool(
        "banner_shown", ui.get("banner_shown", _DEFAULTS_UI["banner_shown"])
    )

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
        find=_validate_accel(
            "find", sc.get("find", _DEFAULTS_SHORTCUTS["find"])
        ),
    )

    cfg = Config(
        path=path,
        coverage=coverage,
        follow_theme=follow_theme,
        background=background,
        transparency=transparency,
        font=font,
        zoom=zoom,
        banner_shown=banner_shown,
        shortcuts=shortcuts,
    )

    if not path.exists():
        save(cfg)

    return cfg


def save(cfg: Config) -> None:
    parser = configparser.ConfigParser()
    parser["ui"] = {
        "coverage": str(cfg.coverage),
        "follow_theme": "true" if cfg.follow_theme else "false",
        "background": cfg.background,
        "transparency": str(cfg.transparency),
        "font": cfg.font,
        "zoom": f"{cfg.zoom:g}",
        "banner_shown": "true" if cfg.banner_shown else "false",
    }
    parser["shortcuts"] = {
        "new_tab": cfg.shortcuts.new_tab,
        "close_tab": cfg.shortcuts.close_tab,
        "rename_tab": cfg.shortcuts.rename_tab,
        "find": cfg.shortcuts.find,
    }
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    with cfg.path.open("w") as f:
        parser.write(f)


def _parse_int_in_range(name: str, value: str, lo: int, hi: int) -> int:
    n = int(value)
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be {lo}..{hi}, got {n}")
    return n


def _parse_float_in_range(name: str, value: str, lo: float, hi: float) -> float:
    n = float(value)
    if not lo <= n <= hi:
        raise ValueError(f"{name} must be {lo}..{hi}, got {n}")
    return n


def _parse_bool(name: str, value: str) -> bool:
    s = value.strip().lower()
    if s in ("true", "yes", "on", "1"):
        return True
    if s in ("false", "no", "off", "0"):
        return False
    raise ValueError(f"{name} must be a boolean, got {value!r}")


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
