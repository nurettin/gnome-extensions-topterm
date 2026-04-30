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

## Shortcuts

```
F1                   toggle dropdown (rebindable: gsettings set org.gnome.shell.extensions.topterm toggle "['F1']")
Ctrl+T / Ctrl+W      new / close tab
F2                   rename current tab
Alt+1..9, Alt+0      jump to tab 1..9, 10
Ctrl+Shift+Up/Down   taller / shorter (5%)
Ctrl+Shift+T / O     more transparent / more opaque (5%)
Ctrl++ / Ctrl+-      zoom in / out  (also Ctrl+Scroll)
Middle-click         paste primary selection
```

## Install

```bash
git clone https://github.com/nurettin/gnome-extensions-topterm.git
cd gnome-extensions-topterm

# Python app (provides the `topterm` entry point and the D-Bus service):
pip install --user .

# GNOME Shell extension (F1 toggle + window placement):
ln -s "$PWD/extension/topterm@nurett.in" \
      ~/.local/share/gnome-shell/extensions/topterm@nurett.in
glib-compile-schemas \
      ~/.local/share/gnome-shell/extensions/topterm@nurett.in/schemas/
# Log out and log back in (Wayland needs a fresh shell to see new extensions)
gnome-extensions enable topterm@nurett.in
```

After that, F1 should drop the terminal down. If it doesn't, the extension calls `~/.local/bin/topterm` to spawn the app the first time — make sure that path is on your `PATH` and that `python3 -m topterm` works.

## Configure

UI/shortcut state lives in `~/.config/topterm/config.ini` and is written automatically when you adjust things at runtime (zoom, height, transparency). Defaults:

```ini
[ui]
coverage = 50          # height as % of monitor (1..100)
background = #1e1e1e
transparency = 0       # 0..100 (% transparent; 0 = opaque)
font = Monospace 12
zoom = 1.0             # vte font scale (0.5..4.0)
banner_shown = false   # welcome banner shown once, then flipped to true

[shortcuts]
new_tab = <Primary>t
close_tab = <Primary>w
rename_tab = F2
```

The F1 toggle accel is a GNOME Shell extension setting (not in `config.ini`):

```bash
gsettings set org.gnome.shell.extensions.topterm toggle "['<Super>grave']"
```

## Requirements

- GNOME Shell 50 (Wayland)
- Python 3.11+, PyGObject, GTK4, libadwaita, VTE 3.91

## License

GPL-2.0-or-later. See `LICENSE`.
