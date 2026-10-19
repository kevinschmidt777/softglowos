"""The setup assistant on the first login: language and keyboard, Wi-Fi,
look, software and devices, one full-screen step at a time.

It starts from autostart (softglowos-hub --setup) until it's finished. A
language change only fully applies after logging in again, so the
assistant logs out right after that step and continues where it left off
(the step is kept in ~/.config/softglowos/setup.json). The preview mode
(--setup-preview) always runs, keeps nothing and doesn't log out."""

import json
import locale
from pathlib import Path

import gi

gi.require_version('NM', '1.0')

from gi.repository import Adw, Gio, GLib, Gtk, NM

from .devices_page import DevicesPage
from .goxlr import Mixer
from .software_page import app_switches

STATE_FILE = Path(GLib.get_user_config_dir()) / 'softglowos' / 'setup.json'

LANGUAGES = (('de_DE.UTF-8', 'Deutsch', 'de'), ('en_US.UTF-8', 'English', 'us'))
KEYBOARDS = (
    ('de', _('German')),
    ('ch', _('German (Switzerland)')),
    ('at', _('German (Austria)')),
    ('us', _('English (US)')),
    ('gb', _('English (UK)')),
    ('fr', _('French')),
    ('es', _('Spanish')),
    ('it', _('Italian')),
    ('nl', _('Dutch')),
    ('pl', _('Polish')),
)
ACCENTS = ('blue', 'teal', 'green', 'yellow', 'orange', 'red', 'pink', 'purple', 'slate')
ACCENT_NAMES = {
    'blue': _('Blue'), 'teal': _('Teal'), 'green': _('Green'), 'yellow': _('Yellow'),
    'orange': _('Orange'), 'red': _('Red'), 'pink': _('Pink'), 'purple': _('Purple'),
    'slate': _('Slate'),
}
NIGHT_THEME_SWITCHER = 'nightthemeswitcher@romainvigier.fr'
WALLPAPERS = '/usr/share/backgrounds/softglowos/softglowos-{}.jpg'


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def setup_done():
    return load_state().get('done', False)


def current_language():
    return (locale.getlocale()[0] or 'en_US') + '.UTF-8'


def _step(title, subtitle, content):
    """A page of the assistant: big title, a line below, the content."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24,
                  valign=Gtk.Align.CENTER, margin_top=48, margin_bottom=24)
    heading = Gtk.Label(label=title, wrap=True, justify=Gtk.Justification.CENTER)
    heading.add_css_class('title-1')
    box.append(heading)
    if subtitle:
        line = Gtk.Label(label=subtitle, wrap=True, justify=Gtk.Justification.CENTER)
        line.add_css_class('dim-label')
        box.append(line)
    box.append(content)
    scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                  child=Adw.Clamp(maximum_size=640, child=box,
                                                  margin_start=24, margin_end=24))
    return scrolled


class SetupWindow(Adw.ApplicationWindow):
    def __init__(self, preview=False, **kwargs):
        super().__init__(title=_('Welcome'), **kwargs)
        self.preview = preview
        self.state = {} if preview else load_state()
        self.settings = Gio.Settings(schema_id='org.gnome.desktop.interface')
        self.nm = NM.Client.new(None)

        self.steps = [('language', self._language_step())]
        if self.nm.get_primary_connection() is None:
            self.steps.append(('wifi', self._wifi_step()))
        self.steps += [
            ('look', self._look_step()),
            ('software', self._software_step()),
            ('devices', self._devices_step()),
            ('done', self._done_step()),
        ]

        self.stack = Gtk.Stack(vexpand=True, transition_duration=300)
        self.dots = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        for step_id, page in self.steps:
            self.stack.add_named(page, step_id)
            dot = Gtk.Box(valign=Gtk.Align.CENTER)
            dot.add_css_class('setup-dot')
            self.dots.append(dot)
        self.position = 0

        self.back = Gtk.Button(label=_('Back'))
        self.back.connect('clicked', lambda _b: self._go(-1))
        self.next = Gtk.Button(label=_('Continue'))
        self.next.add_css_class('suggested-action')
        self.next.connect('clicked', self._on_next)
        bar = Gtk.CenterBox(margin_top=12, margin_bottom=24, margin_start=48, margin_end=48)
        bar.set_start_widget(self.back)
        bar.set_center_widget(self.dots)
        bar.set_end_widget(self.next)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.stack)
        content.append(bar)
        self.set_content(content)
        self.fullscreen()

        # After the logout for a new language: continue where we were
        ids = [step_id for step_id, _page in self.steps]
        resume = self.state.get('step')
        self._show(ids.index(resume) if resume in ids else 0)

    # Navigation

    def _index(self):
        return self.position

    def _go(self, delta):
        self._show(min(max(self.position + delta, 0), len(self.steps) - 1))
        if not self.preview:
            self.state['step'] = self.steps[self.position][0]
            save_state(self.state)

    def _show(self, index):
        self.stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT if index >= self.position
            else Gtk.StackTransitionType.SLIDE_RIGHT)
        self.position = index
        self.stack.set_visible_child_name(self.steps[index][0])
        dot = self.dots.get_first_child()
        number = 0
        while dot:
            if number == index:
                dot.add_css_class('current')
            else:
                dot.remove_css_class('current')
            dot = dot.get_next_sibling()
            number += 1
        self._update_buttons()

    def _update_buttons(self):
        step_id = self.steps[self._index()][0]
        self.back.set_visible(self._index() > 0 and step_id != 'done')
        self.next.set_visible(step_id != 'done')
        self.next.set_sensitive(step_id != 'language' or self.language is not None)

    def _on_next(self, _button):
        if self.steps[self._index()][0] == 'language':
            self._apply_language()
        else:
            self._go(1)

    def _finish(self, _button):
        if not self.preview:
            self.state = {'done': True}
            save_state(self.state)
        self.close()

    # Language and keyboard

    def _language_step(self):
        self.language = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        buttons = Gtk.Box(spacing=12, homogeneous=True)
        self.language_buttons = {}
        group = None
        for code, name, _layout in LANGUAGES:
            button = Gtk.ToggleButton(label=name, group=group)
            button.add_css_class('setup-choice')
            button.connect('toggled', self._on_language_toggled, code)
            buttons.append(button)
            self.language_buttons[code] = button
            group = group or button
        box.append(buttons)

        keyboards = Adw.PreferencesGroup()
        self.keyboard_row = Adw.ComboRow(
            title=_('Keyboard'),
            model=Gtk.StringList.new([name for _layout, name in KEYBOARDS]))
        keyboards.add(self.keyboard_row)
        box.append(keyboards)
        return _step(_('Welcome to SoftglowOS'),
                     _('Pick your language. You can change everything later, too.'), box)

    def _on_language_toggled(self, button, code):
        if not button.get_active():
            return
        self.language = code
        layout = next(layout for c, _name, layout in LANGUAGES if c == code)
        self.keyboard_row.set_selected([k for k, _name in KEYBOARDS].index(layout))
        self._update_buttons()

    def _apply_language(self):
        layout = KEYBOARDS[self.keyboard_row.get_selected()][0]
        Gio.Settings(schema_id='org.gnome.desktop.input-sources').set_value(
            'sources', GLib.Variant('a(ss)', [('xkb', layout)]))
        if self.language.split('.')[0] == current_language().split('.')[0]:
            self._go(1)
            return
        if self.preview:
            self._go(1)
            return
        self._set_language(self.language)
        self._go(1)  # remembers the next step for after the logout
        dialog = Adw.AlertDialog(
            heading=_('One quick restart of your session'),
            body=_('SoftglowOS logs you out once so everything shows up in your '
                   'language. After logging in again, the setup continues here.'))
        dialog.add_response('logout', _('Log out'))
        dialog.set_response_appearance('logout', Adw.ResponseAppearance.SUGGESTED)
        dialog.connect('response', lambda *_args: Gio.Subprocess.new(
            ['gnome-session-quit', '--logout', '--no-prompt'], Gio.SubprocessFlags.NONE))
        dialog.present(self)

    def _set_language(self, code):
        """The user's language in AccountsService (what GDM and the session read)."""
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        path = bus.call_sync(
            'org.freedesktop.Accounts', '/org/freedesktop/Accounts',
            'org.freedesktop.Accounts', 'FindUserByName',
            GLib.Variant('(s)', (GLib.get_user_name(),)), GLib.VariantType('(o)'),
            Gio.DBusCallFlags.NONE, -1, None).unpack()[0]
        bus.call_sync('org.freedesktop.Accounts', path, 'org.freedesktop.Accounts.User',
                      'SetLanguage', GLib.Variant('(s)', (code,)), None,
                      Gio.DBusCallFlags.NONE, -1, None)

    # Wi-Fi

    def _wifi_step(self):
        self.wifi_group = Adw.PreferencesGroup()
        self.wifi_rows = []
        self._fill_wifi()
        self.nm.connect('notify::primary-connection', lambda *_args: self._fill_wifi())
        return _step(_('Get online'),
                     _('For updates, apps and streaming. You can also do this later.'),
                     self.wifi_group)

    def _wifi_device(self):
        return next((d for d in self.nm.get_devices() if isinstance(d, NM.DeviceWifi)), None)

    def _fill_wifi(self):
        for row in self.wifi_rows:
            self.wifi_group.remove(row)
        self.wifi_rows = []
        device = self._wifi_device()
        if self.nm.get_primary_connection() is not None:
            rows = [Adw.ActionRow(title=_('You\'re online'))]
        elif device is None:
            rows = [Adw.ActionRow(title=_('No Wi-Fi found'),
                                  subtitle=_('Plug in a network cable or continue without.'))]
        else:
            device.request_scan_async(None, None, None)
            networks = {}
            for ap in device.get_access_points():
                ssid = ap.get_ssid()
                name = NM.utils_ssid_to_utf8(ssid.get_data()) if ssid else ''
                if name and (name not in networks or ap.get_strength() > networks[name].get_strength()):
                    networks[name] = ap
            rows = []
            for name, ap in sorted(networks.items(), key=lambda item: -item[1].get_strength()):
                row = Adw.ActionRow(title=GLib.markup_escape_text(name), activatable=True)
                if ap.get_rsn_flags() or ap.get_wpa_flags():
                    row.add_suffix(Gtk.Image(icon_name='network-wireless-encrypted-symbolic'))
                row.connect('activated', self._on_network, device, ap, name)
                rows.append(row)
            if not rows:
                GLib.timeout_add_seconds(3, lambda: self._fill_wifi() or GLib.SOURCE_REMOVE)
                rows = [Adw.ActionRow(title=_('Looking for networks …'))]
        for row in rows:
            self.wifi_group.add(row)
            self.wifi_rows.append(row)

    def _on_network(self, _row, device, ap, name):
        connection = NM.SimpleConnection.new()
        setting = NM.SettingConnection.new()
        setting.set_property('id', name)
        connection.add_setting(setting)
        if not (ap.get_rsn_flags() or ap.get_wpa_flags()):
            self.nm.add_and_activate_connection_async(connection, device, ap.get_path(),
                                                      None, None, None)
            return
        entry = Adw.PasswordEntryRow(title=_('Password'))
        dialog = Adw.AlertDialog(heading=name, extra_child=entry)
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('connect', _('Connect'))
        dialog.set_response_appearance('connect', Adw.ResponseAppearance.SUGGESTED)

        def on_response(_dialog, response):
            if response != 'connect':
                return
            security = NM.SettingWirelessSecurity.new()
            security.set_property('key-mgmt', 'wpa-psk')
            security.set_property('psk', entry.get_text())
            connection.add_setting(security)
            self.nm.add_and_activate_connection_async(connection, device, ap.get_path(),
                                                      None, None, None)

        dialog.connect('response', on_response)
        dialog.present(self)

    # Look

    def _look_step(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        modes = Gtk.Box(spacing=12, homogeneous=True)
        current = self._current_mode()
        group = None
        for mode, label in (('light', _('Light')), ('dark', _('Dark')), ('auto', _('Automatic'))):
            preview = Gtk.Box(homogeneous=True, overflow=Gtk.Overflow.HIDDEN)
            preview.add_css_class('setup-preview')
            for variant in (('light', 'dark') if mode == 'auto' else (mode,)):
                picture = Gtk.Picture.new_for_filename(WALLPAPERS.format(variant))
                picture.set_content_fit(Gtk.ContentFit.COVER)
                preview.append(picture)
            tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            tile.append(preview)
            tile.append(Gtk.Label(label=label))
            button = Gtk.ToggleButton(child=tile, group=group, active=mode == current)
            button.add_css_class('setup-tile')
            button.connect('toggled', self._on_mode, mode)
            modes.append(button)
            group = group or button
        box.append(modes)

        accents = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        current_accent = self.settings.get_string('accent-color')
        group = None
        for accent in ACCENTS:
            button = Gtk.ToggleButton(group=group, active=accent == current_accent,
                                      tooltip_text=ACCENT_NAMES[accent])
            button.update_property([Gtk.AccessibleProperty.LABEL], [ACCENT_NAMES[accent]])
            button.add_css_class('accent-swatch')
            button.add_css_class(accent)
            button.connect('toggled', lambda b, a=accent: b.get_active()
                           and self.settings.set_string('accent-color', a))
            accents.append(button)
            group = group or button
        caption = Gtk.Label(label=_('Accent color'))
        caption.add_css_class('heading')
        box.append(caption)
        box.append(accents)
        return _step(_('Choose your look'),
                     _('Automatic switches between light and dark with the time of day.'), box)

    def _current_mode(self):
        enabled = Gio.Settings(schema_id='org.gnome.shell').get_strv('enabled-extensions')
        if NIGHT_THEME_SWITCHER in enabled:
            return 'auto'
        return 'dark' if self.settings.get_string('color-scheme') == 'prefer-dark' else 'light'

    def _on_mode(self, button, mode):
        if not button.get_active():
            return
        self._shell_extension('EnableExtension' if mode == 'auto' else 'DisableExtension')
        if mode != 'auto':
            self.settings.set_string('color-scheme', f'prefer-{mode}')

    def _shell_extension(self, method):
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
            'org.gnome.Shell.Extensions', '/org/gnome/Shell/Extensions',
            'org.gnome.Shell.Extensions', method, GLib.Variant('(s)', (NIGHT_THEME_SWITCHER,)),
            None, Gio.DBusCallFlags.NONE, -1, None, None, None)

    # Software, devices, done

    def _software_step(self):
        group = Adw.PreferencesGroup()
        app_switches(group)
        return _step(_('Your apps'),
                     _('Everything is installed. Switch off what you don\'t need, '
                       'it only disappears from the app grid and the dock.'), group)

    def _devices_step(self):
        page = DevicesPage(Mixer())
        page.set_vexpand(True)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(page)
        page.set_size_request(-1, 420)
        return _step(_('Your devices'),
                     _('Plug in what you stream with. The Hub sets it up for you.'), box)

    def _done_step(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        icon = Gtk.Image(icon_name='com.softglowos.Hub', pixel_size=128)
        box.append(icon)
        button = Gtk.Button(label=_('Let\'s go'), halign=Gtk.Align.CENTER)
        button.add_css_class('suggested-action')
        button.add_css_class('setup-finish')
        button.connect('clicked', self._finish)
        box.append(button)
        return _step(_('All set'),
                     _('Mixer, devices, software and updates are always in the Hub.'), box)
