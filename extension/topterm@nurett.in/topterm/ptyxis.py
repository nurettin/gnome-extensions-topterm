import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib

PTYXIS_SCHEMA = "org.gnome.Ptyxis"
PROFILE_SCHEMA = "org.gnome.Ptyxis.Profile"
USER_PALETTE_DIR = Path.home() / ".local/share/org.gnome.Ptyxis/palettes"
GRESOURCE_PALETTE_PATH = "/org/gnome/Ptyxis/palettes"


@dataclass(frozen=True)
class PtyxisColors:
    fg: str
    bg: str
    palette: tuple[str, ...]  # length 16


@dataclass(frozen=True)
class PtyxisTheme:
    light: PtyxisColors
    dark: PtyxisColors
    font: str | None  # None if Ptyxis is using system monospace


def detect() -> PtyxisTheme | None:
    schema_source = Gio.SettingsSchemaSource.get_default()
    if schema_source is None:
        return None
    if schema_source.lookup(PTYXIS_SCHEMA, True) is None:
        return None
    if schema_source.lookup(PROFILE_SCHEMA, True) is None:
        return None

    s = Gio.Settings(schema_id=PTYXIS_SCHEMA)
    uuid = s.get_string("default-profile-uuid")
    if not uuid:
        return None

    profile = Gio.Settings.new_with_path(
        PROFILE_SCHEMA, f"/org/gnome/Ptyxis/Profiles/{uuid}/"
    )
    palette_name = profile.get_string("palette")
    if not palette_name:
        return None

    palette_text = _read_palette_file(palette_name)
    if palette_text is None:
        return None

    light, dark = _parse_palette(palette_text)
    if light is None or dark is None:
        return None

    use_system_font = s.get_boolean("use-system-font")
    font = None if use_system_font else (s.get_string("font-name") or None)

    return PtyxisTheme(light=light, dark=dark, font=font)


def _read_palette_file(name: str) -> str | None:
    for fname in (f"{name}.palette", f"{name.lower()}.palette"):
        p = USER_PALETTE_DIR / fname
        if p.is_file():
            return p.read_text()

    ptyxis_bin = shutil.which("ptyxis")
    if ptyxis_bin is None:
        return None
    seen: set[str] = set()
    for cand in (name, name.lower(), name.title(), name.upper()):
        if cand in seen:
            continue
        seen.add(cand)
        try:
            r = subprocess.run(
                ["gresource", "extract", ptyxis_bin,
                 f"{GRESOURCE_PALETTE_PATH}/{cand}.palette"],
                capture_output=True, text=True, timeout=2, check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if r.returncode == 0 and r.stdout:
            return r.stdout
    return None


def _parse_palette(text: str) -> tuple[PtyxisColors | None, PtyxisColors | None]:
    kf = GLib.KeyFile.new()
    try:
        kf.load_from_data(text, len(text), GLib.KeyFileFlags.NONE)
    except GLib.Error:
        return None, None
    return _section(kf, "Light"), _section(kf, "Dark")


def _section(kf: GLib.KeyFile, name: str) -> PtyxisColors | None:
    if not kf.has_group(name):
        return None
    try:
        fg = kf.get_string(name, "Foreground")
        bg = kf.get_string(name, "Background")
        palette = tuple(kf.get_string(name, f"Color{i}") for i in range(16))
    except GLib.Error:
        return None
    return PtyxisColors(fg=fg, bg=bg, palette=palette)
