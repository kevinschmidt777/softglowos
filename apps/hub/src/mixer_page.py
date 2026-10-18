from gi.repository import Adw, Gtk

from .strips import ChannelStrip, MicStrip
from .widgets import DevicePicker, EqDialog

CHANNEL_NAMES = {
    'game': _('Game'),
    'chat': _('Chat'),
    'music': _('Music'),
    'system': _('System'),
    'browser': _('Browser'),
    'console': _('Console'),
}


@Gtk.Template(resource_path='/com/softglowos/Hub/mixer-page.ui')
class MixerPage(Adw.Bin):
    __gtype_name__ = 'MixerPage'

    stack = Gtk.Template.Child()
    output_box = Gtk.Template.Child()
    stream_label = Gtk.Template.Child()
    strips = Gtk.Template.Child()

    def __init__(self, mixer, **kwargs):
        super().__init__(**kwargs)
        self.mixer = mixer

        self.output_picker = DevicePicker(mixer.outputs, mixer.set_output,
                                          markup=_('Listening on <b>{device}</b>'))
        self.output_box.append(self.output_picker)
        self.stream_label.set_markup(_('Stream goes to <b>{target}</b>').format(
            target='OBS'))

        self.mic_picker = DevicePicker(mixer.microphones, mixer.set_microphone,
                                       empty_label=_('No microphone'), small=True)
        self.mic = MicStrip(self.mic_picker)
        self.mic.connect('level-changed', lambda _s, value: mixer.set_mic(value))
        self.mic.connect('mute-changed', lambda _s, muted: mixer.set_mic_muted(muted))
        self.mic.connect('filter-changed', lambda _s, name, on: mixer.set_filter(name, on))
        self.mic.connect('eq-requested', self._on_eq_requested)
        self.strips.append(self.mic)

        self.channels = {}
        for channel_id, name in CHANNEL_NAMES.items():
            picker = None
            if channel_id == 'console':
                picker = DevicePicker(mixer.capture_cards, mixer.set_capture_card,
                                      empty_label=_('No capture card'), small=True)
                self.capture_picker = picker
            strip = ChannelStrip(channel_id, name, device_picker=picker,
                                 with_offset=channel_id == 'console')
            strip.connect('fader-changed', self._on_fader_changed)
            strip.connect('mute-changed', self._on_mute_changed)
            strip.connect('app-dropped', self._on_app_dropped)
            strip.connect('offset-changed',
                          lambda _s, ms: mixer.set_console_offset_ms(ms))
            self.channels[channel_id] = strip
            self.strips.append(strip)

        mixer.connect('changed', lambda _mixer: self.refresh())
        mixer.connect('levels', self._on_levels)
        self.connect('map', lambda _page: mixer.start_meters())
        self.connect('unmap', lambda _page: mixer.stop_meters())

        self.refresh()
        self.mic.set_filters(mixer.filters())
        self.channels['console'].set_offset_ms(mixer.console_offset_ms())

    def refresh(self):
        """Reads every value from the mixer again."""
        if not self.mixer.available():
            self.stack.set_visible_child_name('missing')
            return
        self.stack.set_visible_child_name('mixer')

        self.output_picker.set_device(self.mixer.current_output())
        self.mic_picker.set_device(self.mixer.current_microphone())
        self.capture_picker.set_device(self.mixer.current_capture_card())
        self.mic.set_state(*self.mixer.mic())
        apps = self.mixer.apps()
        for channel_id, strip in self.channels.items():
            for mix, fader in strip.faders.items():
                fader.set_state(*self.mixer.fader(channel_id, mix))
            strip.set_apps(apps.get(channel_id, []))

    def _on_fader_changed(self, strip, mix, value):
        self.mixer.set_fader(strip.channel_id, mix, value)

    def _on_mute_changed(self, strip, mix, muted):
        self.mixer.set_fader_muted(strip.channel_id, mix, muted)

    def _on_app_dropped(self, strip, app):
        self.mixer.move_app(app, strip.channel_id)

    def _on_levels(self, _mixer, levels):
        self.mic.fader.set_level(levels.get('mic', 0))
        for channel_id, strip in self.channels.items():
            for fader in strip.faders.values():
                fader.set_level(levels.get(channel_id, 0))

    def _on_eq_requested(self, _strip):
        filters = self.mixer.filters()
        dialog = EqDialog(self.mixer.eq_bands(), filters['eq'], self.mixer.eq_range_db(),
                          self.mixer.set_eq_gain)
        dialog.present(self)
