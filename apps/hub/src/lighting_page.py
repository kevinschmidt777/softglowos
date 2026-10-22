import queue
import threading
import traceback

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk

from . import lighting

OPENRGB_ID = 'org.openrgb.OpenRGB.desktop'
# Waits this long after the last move of a slider or the color before the
# lighting changes, so dragging doesn't queue up dozens of changes
APPLY_DELAY_MS = 150


class Lighting(GObject.Object):
    """The connection to the OpenRGB server, in a thread of its own (the SDK
    blocks). state: idle, connecting, ready, none (no devices) or failed."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.state = 'idle'
        self.settings = lighting.load_settings()
        self.device_count = 0
        self.effects = ['static']
        self._client = None
        self._pending = None
        self._apply_timer = 0
        self._jobs = queue.Queue()
        threading.Thread(target=self._work, daemon=True).start()

    def connect_server(self):
        if self.state in ('connecting', 'ready'):
            return
        self._set('connecting')
        self._jobs.put(self._connect)

    def change(self, **values):
        self.settings.update(values)
        lighting.save_settings(self.settings)
        if self._apply_timer:
            GLib.source_remove(self._apply_timer)
        self._apply_timer = GLib.timeout_add(APPLY_DELAY_MS, self._queue_apply)

    def _queue_apply(self):
        self._apply_timer = 0
        self._pending = dict(self.settings)
        self._jobs.put(self._apply)
        return GLib.SOURCE_REMOVE

    # In the thread

    def _work(self):
        while True:
            job = self._jobs.get()
            try:
                job()
            except Exception:  # no server, or it went away
                traceback.print_exc()
                self._client = None
                GLib.idle_add(self._set, 'failed')

    def _connect(self):
        lighting.start_service()
        self._client = lighting.connect()
        GLib.idle_add(self._connected, len(self._client.devices), lighting.effects(self._client))

    def _apply(self):
        settings, self._pending = self._pending, None
        if settings is None or self._client is None:
            return  # a newer change already went through
        lighting.apply(self._client, settings)
        lighting.save_profile(self._client, settings)
        GLib.idle_add(self._saved, settings['devices'])
        lighting.enable_service()

    # Back in the main loop

    def _connected(self, count, effects):
        self.device_count = count
        self.effects = effects
        self._set('ready' if count else 'none')

    def _saved(self, devices):
        self.settings['devices'] = devices
        lighting.save_settings(self.settings)

    def _set(self, state):
        self.state = state
        self.emit('changed')


def open_openrgb(_button=None):
    """The OpenRGB app connects to our server when that runs, instead of
    driving the hardware a second time."""
    info = Gio.DesktopAppInfo.new(OPENRGB_ID)
    if info:
        info.launch([], None)
    else:
        Gio.Subprocess.new(['openrgb'], Gio.SubprocessFlags.NONE)



def _status_button(label, callback, suggested=False):
    button = Gtk.Button(label=label, halign=Gtk.Align.CENTER)
    button.add_css_class('pill')
    if suggested:
        button.add_css_class('suggested-action')
    button.connect('clicked', callback)
    return button


class LightingPage(Gtk.Stack):
    """One color, effect and brightness for all RGB lighting, the details
    in the OpenRGB app."""

    def __init__(self, **kwargs):
        super().__init__(transition_type=Gtk.StackTransitionType.CROSSFADE, **kwargs)
        self.lighting = Lighting()
        self.lighting.connect('changed', lambda _lighting: self._show())
        self._updating = False

        loading = Adw.StatusPage(title=_('Looking for lighting …'))
        loading.set_paintable(Adw.SpinnerPaintable(widget=loading))
        self.add_named(loading, 'connecting')

        none = Adw.StatusPage(icon_name='weather-clear-night-symbolic',
                              title=_('No RGB lighting found'),
                              description=_('OpenRGB found nothing it can control.'))
        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        buttons.append(_status_button(_('Search again'), self._retry, suggested=True))
        buttons.append(_status_button(_('Open OpenRGB'), open_openrgb))
        none.set_child(buttons)
        self.add_named(none, 'none')

        failed = Adw.StatusPage(icon_name='dialog-warning-symbolic',
                                title=_('OpenRGB isn\'t answering'),
                                child=_status_button(_('Try again'), self._retry, suggested=True))
        self.add_named(failed, 'failed')

        self.add_named(self._build_settings(), 'ready')
        self.connect('map', lambda _page: self.lighting.connect_server())
        self._show()

    def _build_settings(self):
        settings = self.lighting.settings
        page = Adw.PreferencesPage()

        main = Adw.PreferencesGroup()
        self.on_row = Adw.SwitchRow(title=_('Lighting'), active=settings['on'])
        self.on_row.connect('notify::active', self._on_switch)
        main.add(self.on_row)
        page.add(main)

        self.look = Adw.PreferencesGroup()
        self.effect_row = Adw.ComboRow(title=_('Effect'))
        self.effect_row.connect('notify::selected', self._on_effect)
        self.look.add(self.effect_row)

        self.color_row = Adw.ActionRow(title=_('Color'))
        self.color_button = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False),
                                                  valign=Gtk.Align.CENTER)
        rgba = Gdk.RGBA()
        rgba.parse(settings['color'])
        self.color_button.set_rgba(rgba)
        self.color_button.connect('notify::rgba', self._on_color)
        self.color_row.add_suffix(self.color_button)
        self.look.add(self.color_row)

        brightness_row = Adw.ActionRow(title=_('Brightness'))
        self.brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.brightness.set_value(settings['brightness'])
        self.brightness.set_hexpand(True)
        self.brightness.set_size_request(200, -1)
        self.brightness.update_property([Gtk.AccessibleProperty.LABEL], [_('Brightness')])
        self.brightness.connect('value-changed', lambda scale:
                                self.lighting.change(brightness=int(scale.get_value())))
        brightness_row.add_suffix(self.brightness)
        self.look.add(brightness_row)
        page.add(self.look)

        more = Adw.PreferencesGroup()
        openrgb_row = Adw.ActionRow(title=_('Advanced settings'),
                                    subtitle=_('Single devices, zones and effects'))
        openrgb_button = Gtk.Button(label=_('Open OpenRGB'), valign=Gtk.Align.CENTER)
        openrgb_button.connect('clicked', open_openrgb)
        openrgb_row.add_suffix(openrgb_button)
        more.add(openrgb_row)
        page.add(more)
        return page

    def _show(self):
        state = self.lighting.state
        self.set_visible_child_name('connecting' if state == 'idle' else state)
        if state != 'ready':
            return
        count = self.lighting.device_count
        self.on_row.set_subtitle(_('One device') if count == 1
                                 else _('{count} devices').format(count=count))
        labels = {'static': _('Static'), 'rainbow': _('Rainbow')}
        self._updating = True
        self.effect_row.set_model(Gtk.StringList.new([labels[e] for e in self.lighting.effects]))
        effect = self.lighting.settings['effect']
        if effect in self.lighting.effects:
            self.effect_row.set_selected(self.lighting.effects.index(effect))
        self._updating = False
        self._show_sensitivity()

    def _show_sensitivity(self):
        settings = self.lighting.settings
        self.look.set_sensitive(settings['on'])
        self.color_row.set_sensitive(settings['effect'] != 'rainbow')

    def _retry(self, _button):
        self.lighting.connect_server()

    def _on_switch(self, row, _param):
        self.lighting.change(on=row.get_active())
        self._show_sensitivity()

    def _on_effect(self, row, _param):
        if self._updating:
            return
        self.lighting.change(effect=self.lighting.effects[row.get_selected()])
        self._show_sensitivity()

    def _on_color(self, button, _param):
        rgba = button.get_rgba()
        self.lighting.change(color='#{:02x}{:02x}{:02x}'.format(
            *(round(value * 255) for value in (rgba.red, rgba.green, rgba.blue))))
