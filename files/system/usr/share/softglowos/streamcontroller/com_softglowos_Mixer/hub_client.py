"""Talks to the SoftglowOS Hub, which offers the mixer as D-Bus actions
(see mixer_actions.py in the Hub): mute-<target> toggles on activation,
volume-<target> takes a new value through SetState. <target> is "mic" or
"<channel>-<mix>" with mix "stream" or "monitor". D-Bus starts the Hub if it
isn't running. StreamController may talk to the Hub because SoftglowOS
gives it that right (a flatpak override, set at login)."""

import threading

from gi.repository import Gio, GLib

NAME = 'com.softglowos.Hub'
PATH = '/com/softglowos/Hub'
IFACE = 'org.gtk.Actions'


class HubClient:
    def __init__(self):
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self._states = {}
        self._listeners = []
        self._lock = threading.Lock()
        self._bus.signal_subscribe(NAME, IFACE, 'Changed', PATH, None,
                                   Gio.DBusSignalFlags.NONE, self._on_changed)
        # A (re)started Hub sends no Changed for its first states
        Gio.bus_watch_name_on_connection(self._bus, NAME, Gio.BusNameWatcherFlags.NONE,
                                         lambda *_args: self.refresh(), None)

    def listen(self, callback):
        """callback(name, value) for every state that changes."""
        self._listeners.append(callback)

    def state(self, name, default=None):
        with self._lock:
            return self._states.get(name, default)

    def refresh(self):
        self._bus.call(NAME, PATH, IFACE, 'DescribeAll', None, None,
                       Gio.DBusCallFlags.NONE, 5000, None, self._on_described)

    def toggle_mute(self, target):
        self._call('Activate', GLib.Variant('(sava{sv})', (f'mute-{target}', [], {})))

    def set_volume(self, target, value):
        value = max(0, min(100, int(value)))
        self._call('SetState', GLib.Variant('(sva{sv})', (f'volume-{target}', GLib.Variant('i', value), {})))

    def _call(self, method, parameters):
        self._bus.call(NAME, PATH, IFACE, method, parameters, None,
                       Gio.DBusCallFlags.NONE, 10000, None, None)

    def _on_described(self, bus, result):
        try:
            actions = bus.call_finish(result).unpack()[0]
        except GLib.Error:
            return  # Hub not there (yet): Changed signals fill in later
        for name, (_enabled, _signature, state) in actions.items():
            if state:
                self._set(name, state[0])

    def _on_changed(self, _bus, _sender, _path, _iface, _signal, parameters):
        _removed, _enabled, states, added = parameters.unpack()
        for name, value in states.items():
            self._set(name, value)
        for name, (_enabled, _signature, state) in added.items():
            if state:
                self._set(name, state[0])

    def _set(self, name, value):
        with self._lock:
            self._states[name] = value
        for callback in self._listeners:
            callback(name, value)
