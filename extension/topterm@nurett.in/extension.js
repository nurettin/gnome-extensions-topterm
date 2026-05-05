import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const APP_ID = 'in.nurett.topterm';
const APP_OBJECT_PATH = '/in/nurett/topterm';
const TOGGLE_KEY = 'toggle';
const SPAWN_GRACE_SECONDS = 5;
const DEPS_HINT = 'Install python3, PyGObject, GTK4, libadwaita, and VTE 3.91.';

export default class TopTermExtension extends Extension {
    enable() {
        this._settings = this.getSettings();

        this._windowSignal = global.display.connect(
            'window-created',
            (_display, win) => this._onWindowCreated(win)
        );

        this._addKeybinding();

        // Re-bind whenever the user changes the toggle accel from prefs.
        this._toggleChangedId = this._settings.connect(
            `changed::${TOGGLE_KEY}`,
            () => {
                Main.wm.removeKeybinding(TOGGLE_KEY);
                this._addKeybinding();
            }
        );
    }

    disable() {
        if (this._depsCheckId) {
            GLib.source_remove(this._depsCheckId);
            this._depsCheckId = null;
        }
        if (this._toggleChangedId) {
            this._settings.disconnect(this._toggleChangedId);
            this._toggleChangedId = null;
        }
        Main.wm.removeKeybinding(TOGGLE_KEY);
        if (this._windowSignal) {
            global.display.disconnect(this._windowSignal);
            this._windowSignal = null;
        }
        this._settings = null;
    }

    _addKeybinding() {
        Main.wm.addKeybinding(
            TOGGLE_KEY,
            this._settings,
            Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL,
            () => this._toggle()
        );
    }

    _toggle() {
        Gio.DBus.session.call(
            APP_ID, APP_OBJECT_PATH, 'org.gtk.Actions', 'Activate',
            new GLib.Variant('(sava{sv})', [TOGGLE_KEY, [], {}]),
            null, Gio.DBusCallFlags.NONE, -1, null,
            (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (_e) {
                    // App isn't running yet; launching it will register on the bus
                    // and the first window will appear.
                    this._spawnApp();
                }
            }
        );
    }

    _spawnApp() {
        // Bundled Python source lives in `<extension-dir>/topterm/`. Running
        // `python3 -m topterm` with cwd=this.path puts the bundled package on
        // sys.path[0] without needing PYTHONPATH or a `pip install`.
        try {
            GLib.spawn_async(
                this.path,
                ['python3', '-m', 'topterm'],
                null,
                GLib.SpawnFlags.SEARCH_PATH
                    | GLib.SpawnFlags.STDOUT_TO_DEV_NULL
                    | GLib.SpawnFlags.STDERR_TO_DEV_NULL,
                null
            );
            this._scheduleDepsCheck();
        } catch (e) {
            Main.notifyError('TopTerm', `python3 not found. ${DEPS_HINT}`);
            logError(e, 'topterm: failed to spawn `python3 -m topterm`');
        }
    }

    _scheduleDepsCheck() {
        // spawn_async only fails synchronously when python3 is absent. If
        // python3 launches but the import of Vte/Adw/Gtk fails, stderr is
        // discarded and the app silently dies without claiming the bus name.
        // Catch that case by polling NameHasOwner after a grace period.
        if (this._depsCheckId)
            GLib.source_remove(this._depsCheckId);
        this._depsCheckId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            SPAWN_GRACE_SECONDS,
            () => {
                this._depsCheckId = null;
                Gio.DBus.session.call(
                    'org.freedesktop.DBus',
                    '/org/freedesktop/DBus',
                    'org.freedesktop.DBus',
                    'NameHasOwner',
                    new GLib.Variant('(s)', [APP_ID]),
                    null, Gio.DBusCallFlags.NONE, -1, null,
                    (conn, res) => {
                        try {
                            const [hasOwner] = conn.call_finish(res).deepUnpack();
                            if (!hasOwner)
                                Main.notifyError('TopTerm', `Failed to start. ${DEPS_HINT}`);
                        } catch (_e) {}
                    }
                );
                return GLib.SOURCE_REMOVE;
            }
        );
    }

    _onWindowCreated(win) {
        if (win.get_gtk_application_id?.() === APP_ID) {
            this._attachWindow(win);
            return;
        }
        // GTK4/Wayland sometimes sets the id slightly after window-created.
        const handler = win.connect('notify::gtk-application-id', () => {
            if (win.get_gtk_application_id?.() === APP_ID) {
                win.disconnect(handler);
                this._attachWindow(win);
            }
        });
    }

    _attachWindow(win) {
        // Position on every map (initial show + every re-show after hide),
        // because mutter's placement runs after window-created, and GTK can
        // reset its preferred size when re-mapped.
        const mapHandler = global.window_manager.connect('map', (_wm, actor) => {
            if (actor.meta_window === win)
                this._positionDropdown(win);
        });
        win.connect('unmanaged', () => {
            global.window_manager.disconnect(mapHandler);
        });
        const actor = win.get_compositor_private();
        if (actor && actor.visible)
            this._positionDropdown(win);
    }

    _positionDropdown(win) {
        const monitorIdx = global.display.get_primary_monitor();
        const geom = global.display.get_monitor_geometry(monitorIdx);
        const coverage = this._readCoverage();
        const height = Math.max(100, Math.floor(geom.height * (coverage / 100)));
        // move_frame first (user_op=true) anchors position on Wayland before
        // the resize; ddterm relies on this two-step.
        win.move_frame(true, geom.x, geom.y);
        win.move_resize_frame(false, geom.x, geom.y, geom.width, height);
        win.make_above();
        win.stick();
        // Ensure focus so hide-on-focus-loss works on Wayland.
        Main.activateWindow(win);
    }

    _readCoverage() {
        const path = GLib.build_filenamev([
            GLib.get_user_config_dir(), 'topterm', 'config.ini'
        ]);
        const [ok, contents] = GLib.file_get_contents(path);
        if (!ok) return 50;
        const text = new TextDecoder().decode(contents);
        const m = text.match(/^\s*coverage\s*=\s*(\d+)/m);
        if (!m) return 50;
        const v = parseInt(m[1], 10);
        if (!Number.isFinite(v) || v < 1 || v > 100) return 50;
        return v;
    }
}
