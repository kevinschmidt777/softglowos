"""Changes the volume of a channel or the mic. On a key: one step louder or
quieter per press. On a dial (Stream Deck +): turning changes it, pressing
mutes."""

from src.backend.DeckManagement.InputIdentifier import Input

import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk

from ..texts import t
from .TargetAction import CLEAR, MUTED_COLOR, TargetAction

DEFAULT_STEP = 5


class Volume(TargetAction):
    @property
    def step(self):
        return int(self.get_settings().get('step', DEFAULT_STEP))

    @property
    def louder(self):
        return self.get_settings().get('direction', 'up') == 'up'

    def is_dial(self):
        return isinstance(self.input_ident, Input.Dial)

    def event_callback(self, event, data=None):
        if event == Input.Dial.Events.TURN_CW:
            self.change(self.step)
        elif event == Input.Dial.Events.TURN_CCW:
            self.change(-self.step)
        elif event == Input.Dial.Events.DOWN:
            mute = not self.is_muted()
            for target in self.targets():
                if bool(self.hub.state(f'mute-{target}')) != mute:
                    self.hub.toggle_mute(target)
        elif event == Input.Key.Events.DOWN:
            self.change(self.step if self.louder else -self.step)

    def change(self, delta):
        for target in self.targets():
            value = self.hub.state(f'volume-{target}')
            if value is not None:
                self.hub.set_volume(target, value + delta)

    def get_config_rows(self):
        rows = super().get_config_rows()
        directions = ('up', 'down')
        direction = Adw.ComboRow(title=t('direction'),
                                 model=Gtk.StringList.new([t(d) for d in directions]))
        direction.set_selected(directions.index(self.get_settings().get('direction', 'up')))
        direction.connect('notify::selected', lambda row, _p: self._save('direction', directions[row.get_selected()]))
        direction.set_visible(not self.is_dial())
        step = Adw.SpinRow.new_with_range(1, 25, 1)
        step.set_title(t('step'))
        step.set_value(self.step)
        step.connect('notify::value', lambda row, _p: self._save('step', int(row.get_value())))
        return rows + [direction, step]

    def _save(self, key, value):
        settings = self.get_settings()
        settings[key] = value
        self.set_settings(settings)
        self.redraw()

    def redraw(self):
        muted = self.is_muted()
        if self.is_dial():
            self.set_media(media_path=self.speaker_icon(muted), size=0.6)
            self.set_background_color(MUTED_COLOR if muted else CLEAR)
        else:
            self.set_media(media_path=self.icon('plus' if self.louder else 'minus'), size=0.55)
        value = self.volume()
        self.labels()
        self.set_center_label('' if value is None else f'{value} %', font_size=16)
