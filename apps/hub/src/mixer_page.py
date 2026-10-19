from gi.repository import Adw, GLib, Gtk

from .strips import ChannelStrip, MicStrip
from .widgets import DevicePicker, EqDialog

FADER_CHOICE_NAMES = {
    'mic': _('Microphone'),
    'game': _('Game'),
    'chat': _('Chat'),
    'music': _('Music'),
    'system': _('System'),
}

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
        self.mic.connect('offset-changed', lambda _s, ms: mixer.set_offset_ms('mic', ms))
        self.mic.badge.set_popover(self._fader_menu('mic'))
        self.strips.append(self.mic)

        self.channels = {}
        for channel_id, name in CHANNEL_NAMES.items():
            picker = None
            if channel_id == 'console':
                picker = DevicePicker(mixer.capture_cards, mixer.set_capture_card,
                                      empty_label=_('No capture card'), small=True)
                self.capture_picker = picker
            strip = ChannelStrip(channel_id, name, device_picker=picker)
            strip.connect('fader-changed', self._on_fader_changed)
            strip.connect('mute-changed', self._on_mute_changed)
            strip.connect('app-dropped', self._on_app_dropped)
            strip.connect('offset-changed',
                          lambda _s, ms, c=channel_id: mixer.set_offset_ms(c, ms))
            strip.badge.set_popover(self._fader_menu(channel_id))
            self.channels[channel_id] = strip
            self.strips.append(strip)

        mixer.connect('changed', lambda _mixer: self.refresh())
        mixer.connect('levels', self._on_levels)
        self.connect('map', lambda _page: mixer.start_meters())
        self.connect('unmap', lambda _page: mixer.stop_meters())

        self.refresh()
        for target, ms in mixer.offsets_ms().items():
            strip = self.mic if target == 'mic' else self.channels[target]
            strip.offset.set_ms(ms)

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
        self.mic.set_badge(self._badge('mic'))
        self.mic.set_filters(self.mixer.filters())
        apps = self.mixer.apps()
        for channel_id, strip in self.channels.items():
            for mix, fader in strip.faders.items():
                fader.set_state(*self.mixer.fader(channel_id, mix))
            strip.set_apps(apps.get(channel_id, []))
            strip.set_badge(self._badge(channel_id))

    def _badge(self, channel_id):
        letter = self.mixer.fader_of(channel_id)
        return _('GoXLR {fader}').format(fader=letter) if letter else None

    def _fader_menu(self, channel_id):
        """Popover of a GoXLR badge: which channel sits on this desk fader."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = Gtk.Label(label=_('On this fader'), xalign=0)
        title.add_css_class('heading')
        box.append(title)
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        rows.add_css_class('boxed-list')
        for choice in self.mixer.fader_choices():
            row = Adw.ActionRow(title=GLib.markup_escape_text(FADER_CHOICE_NAMES[choice]),
                                activatable=True)
            row.choice = choice
            rows.append(row)
        box.append(rows)
        popover = Gtk.Popover(child=box)

        def on_activated(_rows, row):
            popover.popdown()
            letter = self.mixer.fader_of(channel_id)
            if letter:
                self.mixer.put_on_fader(letter, row.choice)

        rows.connect('row-activated', on_activated)
        return popover

    def open_picker(self, picker):
        """Opens the device list for 'output', 'mic' or 'capture'."""
        button = {'output': self.output_picker, 'mic': self.mic_picker,
                  'capture': self.capture_picker}[picker]
        # After the page switch, so the popover has a place to show up
        GLib.idle_add(lambda: button.popup() or GLib.SOURCE_REMOVE)

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
