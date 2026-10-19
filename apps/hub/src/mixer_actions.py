"""The mixer as actions of the Hub on D-Bus (org.gtk.Actions on
/com/softglowos/Hub), for the StreamController plugin:

  mute-<channel>-<mix>    bool state; activating it toggles the mute
  volume-<channel>-<mix>  int32 state 0-100; change it with SetState
  mute-mic, volume-mic    the same for the microphone

<mix> is "stream" or "monitor" (the "Me" mix). They go through the Hub's
mixer, so they work the same with and without a GoXLR."""

from gi.repository import Gio, GLib

from .audio import CHANNELS, MIXES

TARGETS = [('mic', None)] + [(channel, mix) for channel in CHANNELS for mix in MIXES]


def _suffix(channel, mix):
    return channel if mix is None else f'{channel}-{mix}'


class MixerActions:
    def __init__(self, app, mixer):
        self.mixer = mixer
        self.mute = {}
        self.volume = {}
        for channel, mix in TARGETS:
            name = _suffix(channel, mix)
            mute = Gio.SimpleAction.new_stateful(f'mute-{name}', None, GLib.Variant('b', False))
            mute.connect('activate', self._on_mute, channel, mix)
            volume = Gio.SimpleAction.new_stateful(f'volume-{name}', None, GLib.Variant('i', 0))
            volume.connect('change-state', self._on_volume, channel, mix)
            app.add_action(mute)
            app.add_action(volume)
            self.mute[channel, mix] = mute
            self.volume[channel, mix] = volume
        mixer.connect('changed', lambda _mixer: self.sync())
        self.sync()

    def _read(self, channel, mix):
        return self.mixer.mic() if mix is None else self.mixer.fader(channel, mix)

    def sync(self):
        """Mirrors the mixer into the action states (D-Bus sends Changed)."""
        if not self.mixer.available():
            return
        for channel, mix in TARGETS:
            value, muted = self._read(channel, mix)
            if self.volume[channel, mix].get_state().get_int32() != value:
                self.volume[channel, mix].set_state(GLib.Variant('i', value))
            if self.mute[channel, mix].get_state().get_boolean() != muted:
                self.mute[channel, mix].set_state(GLib.Variant('b', muted))

    def _on_mute(self, action, _parameter, channel, mix):
        muted = not action.get_state().get_boolean()
        action.set_state(GLib.Variant('b', muted))
        if mix is None:
            self.mixer.set_mic_muted(muted)
        else:
            self.mixer.set_fader_muted(channel, mix, muted)

    def _on_volume(self, action, value, channel, mix):
        value = max(0, min(100, value.get_int32()))
        action.set_state(GLib.Variant('i', value))
        if mix is None:
            self.mixer.set_mic(value)
        else:
            self.mixer.set_fader(channel, mix, value)
