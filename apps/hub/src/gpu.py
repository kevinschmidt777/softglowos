"""The graphics driver: SoftglowOS ships one image for AMD/Intel and one for
NVIDIA, and switches between them when the card changes.

Checking needs no admin rights (softglowos-gpu-check looks at the PCI
devices and the running image); switching runs softglowos-switch-gpu through
pkexec without a password and stages the fitting image, which becomes active
after a restart. Settings, apps and files all stay."""

import os

from gi.repository import Gio, GLib, GObject

HELPERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(HELPERS, 'softglowos-gpu-check')
SWITCH = os.path.join(HELPERS, 'softglowos-switch-gpu')

CHECK_STATES = ('fits-amd', 'fits-nvidia', 'old-nvidia', 'nvidia', 'amd', 'staged')


class GraphicsDriver(GObject.Object):
    """State: checking, fits-amd, fits-nvidia, old-nvidia, nvidia or amd
    (a switch is needed), switching, staged, failed or unknown."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.state = 'unknown'

    @property
    def needs_switch(self):
        return self.state in ('nvidia', 'amd')

    def check(self):
        self._set('checking')
        process = Gio.Subprocess.new([CHECK], Gio.SubprocessFlags.STDOUT_PIPE)
        process.communicate_utf8_async(None, None, self._on_checked)

    def _on_checked(self, process, result):
        try:
            _ok, stdout, _stderr = process.communicate_utf8_finish(result)
            state = (stdout or '').strip()
        except GLib.Error:
            state = 'unknown'
        self._set(state if state in CHECK_STATES else 'unknown')

    def switch(self):
        self._set('switching')
        process = Gio.Subprocess.new(['pkexec', SWITCH], Gio.SubprocessFlags.NONE)
        process.wait_check_async(None, self._on_switched)

    def _on_switched(self, process, result):
        try:
            process.wait_check_finish(result)
            self._set('staged')
        except GLib.Error:
            self._set('failed')

    def restart(self):
        Gio.Subprocess.new(['systemctl', 'reboot'], Gio.SubprocessFlags.NONE)

    def _set(self, state):
        self.state = state
        self.emit('changed')
