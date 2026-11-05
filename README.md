# topterm

Opinionated dropdown terminal for GNOME Wayland. F1 to toggle, GTK4 + libadwaita + VTE.

## Disclaimer

**This is an AI-assisted personal project.** I vibed it into existence with an LLM. I could have written it manually, I chose not to. I am not a GTK4/VTE expert, I am not a GNOME extension wizard. The code works for me; whether it works for you is your problem.

**This is not a community project.** I will not merge pull requests. I will not respond to issues. I know that is considered a dick move in the open-source community. Consider yourself warned.

If that is a problem for you, fork it.

## Why

`ddterm` exists and works, but the author is talking about abandoning it and the upstream review queue is slow. So I generated one with an LLM.

## What it does

- Dropdown terminal pinned to the top of the primary monitor, height = configurable % of screen
- Tabs (Adw.TabView), per-launch font zoom, transparency, custom background
- F1 toggle keybinding registered through a tiny GNOME Shell extension that talks to the app over D-Bus
- All UI/keybinding state persisted in a plain `~/.config/topterm/config.ini`
- Tabs survive restarts and reboots: each tab's title, directory and foreground command are saved to `~/.local/state/topterm/tabs.json` every 5 seconds. On the next launch a tab that was running Claude Code resumes its session (`claude <flags> --resume <id>`); any other command is typed back at the prompt without running.
- Optional sounds for dropping down, putting away and new output lines, and an optional `style.css` for a theme's own look (a frame, say). Both are off until configured.

## Shortcuts

```
F1                   toggle dropdown (rebindable, see Configure)
Ctrl+Shift+F1        show this help
Ctrl+T / Ctrl+W      new / close tab
F2                   rename current tab
Ctrl+F               find in scrollback (Esc to close)
Alt+1..9, Alt+0      jump to tab 1..9, 10
Ctrl+Shift+Up/Down   shorter / taller (5%)
Ctrl+Shift+T / O     more transparent / more opaque (5%)
Ctrl++ / Ctrl+-      zoom in / out  (also Ctrl+Scroll)
Middle-click         paste primary selection
Ctrl+Shift+V         paste (images shown as blocks)
Ctrl+Click           open URL under pointer
```

## Install

```bash
git clone https://github.com/nurettin/gnome-extensions-topterm.git
ln -s "$PWD/gnome-extensions-topterm/extension/topterm@nurett.in" \
      ~/.local/share/gnome-shell/extensions/topterm@nurett.in
glib-compile-schemas \
      ~/.local/share/gnome-shell/extensions/topterm@nurett.in/schemas/
# Log out and log back in (Wayland needs a fresh shell to see new extensions)
gnome-extensions enable topterm@nurett.in
```

The Python app is bundled inside the extension directory (`extension/topterm@nurett.in/topterm/`) and is spawned by the JS shim via `python3 -m topterm`. No `pip install` step.

If F1 does nothing, the extension probably failed to spawn Python — check `journalctl --user -b _COMM=gnome-shell | grep topterm` and confirm the native deps below are present.

## Configure

UI/shortcut state lives in `~/.config/topterm/config.ini` and is written automatically when you adjust things at runtime (zoom, height, transparency). Defaults:

```ini
[ui]
coverage = 50          # height as % of monitor (1..100)
follow_theme = true    # match GNOME light/dark; ignores `background` when true
background = #1e1e1e   # used only when follow_theme = false
transparency = 0       # 0..100 (% transparent; 0 = opaque)
font = Monospace 12
zoom = 1.0             # vte font scale (0.5..4.0)
banner_shown = false   # welcome banner shown once, then flipped to true

[shortcuts]
new_tab = <Primary>t
close_tab = <Primary>w
rename_tab = F2
find = <Primary>f
paste = <Primary><Shift>v
help = <Primary><Shift>F1

[sounds]
volume = 100           # 0..100; 0 = silent
show =                 # each a sound file, or a glob with one match picked at random each time; empty = silent
hide =
line =                 # a new line in the tab on screen, at most ~7 a second
```

Sounds play only for the tab on screen, while the dropdown is down. They are uploaded to the sound server at startup, so restart topterm after changing them.

A theme can restyle topterm with GTK CSS in `~/.config/topterm/style.css`, which is read at startup and drawn over topterm's own CSS. For example, a frame that leaves the top edge open against the top bar:

```css
window.background {
  border: 8px solid #847e6c;
  border-top-width: 0;
  border-radius: 0 0 10px 10px;
}
```

The F1 toggle accel is a GNOME Shell extension setting (not in `config.ini`):

```bash
gsettings --schemadir ~/.local/share/gnome-shell/extensions/topterm@nurett.in/schemas set org.gnome.shell.extensions.topterm toggle "['<Super>grave']"
```

## Requirements

- GNOME Shell 50 or 51 (Wayland)
- Python 3.11+
- PyGObject (`python3-gobject` / `python3-gi`)
- GTK4 + libadwaita
- VTE 3.91 GIR bindings — Fedora: `vte291-gtk4`, Debian/Ubuntu: `gir1.2-vte-3.91`
- Only when sounds are configured: GSound — Fedora: `gsound`, Debian/Ubuntu: `gir1.2-gsound-1.0`

On a vanilla GNOME 50 install the GTK4/libadwaita typelibs are typically already pulled in by the desktop itself; VTE 3.91 is the one to double-check.

## License

GPL-2.0-or-later. See `LICENSE`.
