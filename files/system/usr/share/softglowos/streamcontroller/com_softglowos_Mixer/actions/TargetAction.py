"""Shared by both actions: which channel (or the mic) and which mix they
work on, the settings rows for that, and redrawing when the Hub reports a
change."""

import os

from src.backend.PluginManager.ActionBase import ActionBase

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from ..texts import t

CHANNELS = ('mic', 'game', 'chat', 'music', 'system', 'browser', 'console')
MIXES = ('stream', 'monitor', 'both')
MUTED_COLOR = [190, 45, 45, 255]
CLEAR = [0, 0, 0, 0]


class TargetAction(ActionBase):
    DEFAULT_CHANNEL = 'game'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hub = self.plugin_base.hub

    # Settings

    @property
    def channel(self):
        return self.get_settings().get('channel', self.DEFAULT_CHANNEL)

    @property
    def mixes(self):
        if self.channel == 'mic':
            return [None]
        mix = self.get_settings().get('mix', 'stream')
        return ['stream', 'monitor'] if mix == 'both' else [mix]

    def targets(self):
        """Hub action targets: "mic" or "<channel>-<mix>"."""
        return ['mic' if mix is None else f'{self.channel}-{mix}' for mix in self.mixes]

    def is_muted(self):
        states = [self.hub.state(f'mute-{target}') for target in self.targets()]
        return all(states) if None not in states else False

    def volume(self):
        return self.hub.state(f'volume-{self.targets()[0]}')

    def get_config_rows(self):
        self.channel_row = self._combo(t('target'), 'channel', CHANNELS, self.DEFAULT_CHANNEL)
        self.mix_row = self._combo(t('mix'), 'mix', MIXES, 'stream')
        self.mix_row.set_visible(self.channel != 'mic')
        return [self.channel_row, self.mix_row]

    def _combo(self, title, key, values, default):
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new([t(v) for v in values]))
        row.set_selected(values.index(self.get_settings().get(key, default)))

        def on_selected(combo, _param):
            settings = self.get_settings()
            settings[key] = values[combo.get_selected()]
            self.set_settings(settings)
            if key == 'channel':
                self.mix_row.set_visible(settings[key] != 'mic')
            self.redraw()

        row.connect('notify::selected', on_selected)
        return row

    # Display

    def on_ready(self):
        self.plugin_base.watch(self)
        if self.volume() is None:
            self.hub.refresh()
        self.redraw()

    def on_hub_state(self, name):
        if name.split('-', 1)[1] in self.targets():
            self.redraw()

    def labels(self):
        """Channel name below, the mix above (none for the mic)."""
        self.set_bottom_label(t(self.channel), font_size=14)
        mix = self.get_settings().get('mix', 'stream')
        self.set_top_label('' if self.channel == 'mic' else t(mix), font_size=12)

    def icon(self, name):
        return os.path.join(self.plugin_base.PATH, 'assets', f'{name}.svg')

    def speaker_icon(self, muted):
        kind = 'mic' if self.channel == 'mic' else 'speaker'
        return self.icon(f'{kind}-muted' if muted else kind)

    def redraw(self):
        raise NotImplementedError
