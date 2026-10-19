"""The small mixer the tray icon opens: one row per channel for either the
stream or the headphone ("Me") mix, plus the mic. It closes as soon as it
loses focus, like a menu. Everything else stays in the Hub."""

from gi.repository import Adw, GLib, Gtk

from .mixer_page import CHANNEL_NAMES

USER_HOLD_US = 500_000  # same as the Hub's faders: ignore echoes while dragging


class MixerRow(Gtk.Box):
    def __init__(self, name, on_change, on_mute):
        super().__init__(spacing=12)
        self._on_change = on_change
        self._on_mute = on_mute
        self._touched = 0

        label = Gtk.Label(label=name, xalign=0, width_chars=9)
        self.append(label)
        self.scale = Gtk.Scale(hexpand=True, draw_value=False,
                               adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1,
                                                         page_increment=10))
        self.scale.update_property([Gtk.AccessibleProperty.LABEL], [name])
        self._value_handler = self.scale.connect('value-changed', self._on_value_changed)
        self.append(self.scale)
        self.mute = Gtk.ToggleButton(tooltip_text=_('Mute'), valign=Gtk.Align.CENTER)
        self.mute.add_css_class('circular')
        self.mute.add_css_class('flat')
        self.mute.add_css_class('mute-button')
        self._mute_handler = self.mute.connect('toggled', self._on_mute_toggled)
        self.append(self.mute)

    def set_state(self, value, muted):
        if GLib.get_monotonic_time() - self._touched > USER_HOLD_US:
            with self.scale.handler_block(self._value_handler):
                self.scale.set_value(value)
        with self.mute.handler_block(self._mute_handler):
            self.mute.set_active(muted)
        self._show_mute(muted)

    def _show_mute(self, muted):
        self.mute.set_icon_name('audio-volume-muted-symbolic' if muted
                                else 'audio-volume-high-symbolic')

    def _on_value_changed(self, scale):
        self._touched = GLib.get_monotonic_time()
        self._on_change(round(scale.get_value()))

    def _on_mute_toggled(self, button):
        self._show_mute(button.get_active())
        self._on_mute(button.get_active())


class MiniMixer(Adw.Window):
    def __init__(self, mixer, on_open_hub, **kwargs):
        super().__init__(title=_('Mixer'), default_width=380, resizable=False, **kwargs)
        self.mixer = mixer
        self.mix = 'stream'

        stream = Gtk.ToggleButton(label=_('Stream'), active=True)
        me = Gtk.ToggleButton(label=_('Me'), group=stream)
        stream.connect('toggled', lambda b: b.get_active() and self._set_mix('stream'))
        me.connect('toggled', lambda b: b.get_active() and self._set_mix('monitor'))
        switcher = Gtk.Box(halign=Gtk.Align.CENTER)
        switcher.add_css_class('linked')
        switcher.append(stream)
        switcher.append(me)

        hub = Gtk.Button(icon_name='go-next-symbolic', tooltip_text=_('Open Hub'))
        hub.connect('clicked', lambda _b: (self.close(), on_open_hub()))
        header = Adw.HeaderBar(title_widget=switcher, show_start_title_buttons=False,
                               show_end_title_buttons=False)
        header.pack_end(hub)

        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_top=12, margin_bottom=18, margin_start=18, margin_end=12)
        self.mic = MixerRow(_('Microphone'), mixer.set_mic, mixer.set_mic_muted)
        rows.append(self.mic)
        rows.append(Gtk.Separator(margin_top=6, margin_bottom=6))
        self.channels = {}
        for channel_id, name in CHANNEL_NAMES.items():
            row = MixerRow(name,
                           lambda value, c=channel_id: mixer.set_fader(c, self.mix, value),
                           lambda muted, c=channel_id: mixer.set_fader_muted(c, self.mix, muted))
            self.channels[channel_id] = row
            rows.append(row)

        self.stack = Gtk.Stack()
        self.stack.add_named(rows, 'mixer')
        self.stack.add_named(Adw.StatusPage(icon_name='audio-volume-muted-symbolic',
                                            title=_('Mixer not available')), 'missing')
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(header)
        self.set_content(view)

        escape = Gtk.ShortcutController()
        escape.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string('Escape'),
                                         action=Gtk.CallbackAction.new(lambda *_a: self.close())))
        self.add_controller(escape)

        self._changed = mixer.connect('changed', lambda _m: self.refresh())
        self.connect('close-request', self._on_close_request)
        # Behaves like a menu: clicking elsewhere closes it
        self.connect('notify::is-active', lambda w, _p: w.get_property('is-active') or w.close())
        self.refresh()

    def _on_close_request(self, _window):
        self.mixer.disconnect(self._changed)
        return False

    def _set_mix(self, mix):
        self.mix = mix
        self.refresh()

    def refresh(self):
        if not self.mixer.available():
            self.stack.set_visible_child_name('missing')
            return
        self.stack.set_visible_child_name('mixer')
        self.mic.set_state(*self.mixer.mic())
        for channel_id, row in self.channels.items():
            row.set_state(*self.mixer.fader(channel_id, self.mix))
