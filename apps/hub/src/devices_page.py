from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

STREAMCONTROLLER_ID = 'com.core447.StreamController.desktop'


def stream_deck_connected():
    """Any Elgato Stream Deck on USB (by the product name the device reports)."""
    for device in Path('/sys/bus/usb/devices').glob('*'):
        try:
            if (device / 'idVendor').read_text().strip() == '0fd9' and \
                    'stream deck' in (device / 'product').read_text().lower():
                return True
        except OSError:
            continue
    return False


class DevicesPage(Adw.PreferencesPage):
    """What's plugged in and what it's used for. A click leads to where the
    device is set up: the mixer's device pickers or StreamController.
    Without open_in_mixer (setup assistant) the list is only for looking."""

    def __init__(self, mixer, open_in_mixer=None, **kwargs):
        super().__init__(**kwargs)
        self.mixer = mixer
        self._open_in_mixer = open_in_mixer

        group = Adw.PreferencesGroup()
        if open_in_mixer:
            group.set_title(_('Detected devices'))
            group.set_description(_('New devices show up here as soon as you plug them in.'))
        self.rows = {}
        for device_id in ('goxlr', 'capture', 'streamdeck', 'mic', 'headphones'):
            row = Adw.ActionRow(activatable=open_in_mixer is not None)
            status = Gtk.Label(valign=Gtk.Align.CENTER)
            status.add_css_class('caption')
            row.add_suffix(status)
            if open_in_mixer:
                row.add_suffix(Gtk.Image(icon_name='go-next-symbolic'))
            row.status = status
            row.connect('activated', self._on_activated, device_id)
            group.add(row)
            self.rows[device_id] = row
        self.add(group)

        mixer.connect('changed', lambda _mixer: self.refresh())
        self.connect('map', lambda _page: self.refresh())
        # USB devices like the Stream Deck come and go as /dev/hidraw* nodes
        self._dev_monitor = Gio.File.new_for_path('/dev').monitor_directory(
            Gio.FileMonitorFlags.NONE, None)
        self._dev_monitor.connect('changed', self._on_dev_changed)

    def refresh(self):
        if not self.get_mapped() or not self.mixer.available():
            return
        goxlr = self.mixer.goxlr_active
        capture = self.mixer.current_capture_card()
        mic = self.mixer.current_microphone()
        output = self.mixer.current_output()

        self._show('goxlr',
                   'GoXLR Mini' if self.mixer.goxlr_model == 'Mini' else 'GoXLR',
                   _('The mixer controls its hardware channels'), goxlr)
        self._show('capture', capture.description if capture else _('Capture card'),
                   _('Its sound goes into the Console channel'), capture is not None)
        self._show('streamdeck', 'Stream Deck', _('Set up in StreamController'),
                   stream_deck_connected())
        self._show('mic', _('Microphone'),
                   mic.description if mic else _('No microphone'), mic is not None)
        self._show('headphones', _('Headphones'),
                   output.description if output else _('No output'), output is not None)

    def _show(self, device_id, title, subtitle, connected):
        row = self.rows[device_id]
        row.set_title(GLib.markup_escape_text(title))
        row.set_subtitle(GLib.markup_escape_text(subtitle))
        row.status.set_label(_('Connected') if connected else _('Not connected'))
        for css, on in (('success', connected), ('dim-label', not connected)):
            if on:
                row.status.add_css_class(css)
            else:
                row.status.remove_css_class(css)

    def _on_dev_changed(self, _monitor, file, _other, event):
        if file.get_basename().startswith('hidraw') and event in (
                Gio.FileMonitorEvent.CREATED, Gio.FileMonitorEvent.DELETED):
            # Give udev a moment to fill in the device's details
            GLib.timeout_add(500, self._refresh_once)

    def _refresh_once(self):
        self.refresh()
        return GLib.SOURCE_REMOVE

    def _on_activated(self, _row, device_id):
        if device_id == 'streamdeck':
            info = Gio.DesktopAppInfo.new(STREAMCONTROLLER_ID)
            if info:
                info.launch([], None)
            return
        self._open_in_mixer({'capture': 'capture', 'mic': 'mic',
                             'headphones': 'output'}.get(device_id))
