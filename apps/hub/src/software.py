"""The curated apps on the Software page, and showing or hiding them.

Hiding is per user and can be undone at any time: the app stays installed,
but a desktop file with Hidden=true in ~/.local/share/applications takes it
out of the app grid and search, one in ~/.config/autostart keeps it from
starting with the session, and it leaves the dock. Showing it again removes
those files and puts it back on its old place in the dock."""

import json
from pathlib import Path

from gi.repository import Gio, GLib

GROUP = 'Desktop Entry'
# Marks a desktop file we hid, and one we wrote ourselves (removed again
# when the app is shown, while files we only edited just lose Hidden).
HIDDEN_KEY = 'X-SoftglowOS-Hidden'
CREATED_KEY = 'X-SoftglowOS-Created'

APPLICATIONS = Path(GLib.get_user_data_dir()) / 'applications'
AUTOSTART = Path(GLib.get_user_config_dir()) / 'autostart'
STATE_FILE = Path(GLib.get_user_config_dir()) / 'softglowos' / 'hub-software.json'

STORE_ID = 'io.github.kolunmi.Bazaar.desktop'


class App:
    def __init__(self, app_id, name, detail, desktop_ids):
        self.id = app_id
        self.name = name
        self.detail = detail
        self._desktop_ids = desktop_ids

    def desktop_ids(self):
        return self._desktop_ids


class LocalApp(App):
    """An app whose launchers live in ~/.local/share/applications
    (DaVinci Resolve from davincibox, Affinity), found by file name."""

    def __init__(self, app_id, name, detail, patterns):
        super().__init__(app_id, name, detail, ())
        self._patterns = patterns

    def desktop_ids(self):
        return tuple(sorted(path.name for pattern in self._patterns
                            for path in APPLICATIONS.glob(pattern)))


APPS = (
    App('obs', 'OBS Studio', _('Stream and record, encoder matched to the graphics card'),
        ('com.obsproject.Studio.desktop',)),
    App('streamcontroller', 'StreamController', _('Controls your Stream Deck'),
        ('com.core447.StreamController.desktop',)),
    App('openrgb', 'OpenRGB', _('Lighting from every vendor'),
        ('org.openrgb.OpenRGB.desktop',)),
    App('steam', 'Steam', _('Game library'),
        ('steam.desktop',)),
    App('heroic', 'Heroic', _('Epic, GOG and Amazon Games'),
        ('com.heroicgameslauncher.hgl.desktop',)),
    App('lutris', 'Lutris', _('More games and launchers'),
        ('net.lutris.Lutris.desktop',)),
    App('discord', 'Discord', _('Chat and voice'),
        ('discord.desktop',)),
    App('chrome', 'Google Chrome', _('Browser'),
        ('google-chrome.desktop',)),
)

RESOLVE = LocalApp('resolve', 'DaVinci Resolve', _('Video editing'),
                   ('DaVinci*.desktop', 'blackmagicraw*.desktop'))
AFFINITY = LocalApp('affinity', 'Affinity', _('Photo, design and layout'),
                    ('com.softglowos.Affinity.desktop',))


def is_installed(app):
    # Not via Gio.DesktopAppInfo: it treats hidden apps as missing.
    for desktop_id in app.desktop_ids():
        own = APPLICATIONS / desktop_id
        if own.exists() and not _flag(_load(own), CREATED_KEY):
            return True
        if any((Path(directory) / 'applications' / desktop_id).exists()
               for directory in GLib.get_system_data_dirs()):
            return True
    return False


def is_shown(app):
    return not any(_is_hidden(APPLICATIONS / desktop_id) for desktop_id in app.desktop_ids())


def set_shown(app, shown):
    for desktop_id in app.desktop_ids():
        if shown:
            _unhide(APPLICATIONS / desktop_id)
            _unhide(AUTOSTART / desktop_id)
        else:
            _hide(APPLICATIONS / desktop_id, app.name)
            if (AUTOSTART / desktop_id).exists() or _system_autostart(desktop_id):
                _hide(AUTOSTART / desktop_id, app.name)
    _update_dock(app, shown)


def open_store():
    """Opens Bazaar for all the apps we don't curate. False if it's missing."""
    info = Gio.DesktopAppInfo.new(STORE_ID)
    if info is None:
        return False
    info.launch([], None)
    return True


def _load(path):
    keyfile = GLib.KeyFile()
    keyfile.load_from_file(str(path), GLib.KeyFileFlags.KEEP_COMMENTS
                           | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    return keyfile


def _flag(keyfile, key):
    try:
        return keyfile.get_boolean(GROUP, key)
    except GLib.Error:
        return False


def _is_hidden(path):
    if not path.exists():
        return False
    try:
        return _flag(_load(path), HIDDEN_KEY)
    except GLib.Error:
        return False


def _hide(path, name):
    if path.exists():
        keyfile = _load(path)
    else:
        keyfile = GLib.KeyFile()
        keyfile.set_string(GROUP, 'Type', 'Application')
        keyfile.set_string(GROUP, 'Name', name)
        keyfile.set_boolean(GROUP, CREATED_KEY, True)
    keyfile.set_boolean(GROUP, 'Hidden', True)
    keyfile.set_boolean(GROUP, HIDDEN_KEY, True)
    path.parent.mkdir(parents=True, exist_ok=True)
    keyfile.save_to_file(str(path))


def _unhide(path):
    if not _is_hidden(path):
        return
    keyfile = _load(path)
    if _flag(keyfile, CREATED_KEY):
        path.unlink()
        return
    keyfile.remove_key(GROUP, 'Hidden')
    keyfile.remove_key(GROUP, HIDDEN_KEY)
    keyfile.save_to_file(str(path))


def _system_autostart(desktop_id):
    return any((Path(directory) / 'autostart' / desktop_id).exists()
               for directory in GLib.get_system_config_dirs())


def _update_dock(app, shown):
    settings = Gio.Settings(schema_id='org.gnome.shell')
    favorites = list(settings.get_strv('favorite-apps'))
    state = _read_state()
    places = state.setdefault('dock', {})

    if shown:
        for desktop_id in app.desktop_ids():
            if desktop_id in places and desktop_id not in favorites:
                favorites.insert(min(places.pop(desktop_id), len(favorites)), desktop_id)
    else:
        for desktop_id in app.desktop_ids():
            if desktop_id in favorites:
                places[desktop_id] = favorites.index(desktop_id)
                favorites.remove(desktop_id)

    settings.set_strv('favorite-apps', favorites)
    _write_state(state)


def _read_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _write_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))
