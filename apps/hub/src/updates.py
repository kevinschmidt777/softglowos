"""System updates for the Settings page.

Checking needs no admin rights (softglowos-update-check compares image
digests); installing asks for the admin password once through pkexec and
stages the new image, which becomes active after a restart."""

import os

from gi.repository import Gio, GLib, GObject

HELPERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(HELPERS, 'softglowos-update-check')
INSTALL = os.path.join(HELPERS, 'softglowos-update')
SWITCH_CHANNEL = os.path.join(HELPERS, 'softglowos-switch-channel')


def version():
    """The SoftglowOS version from os-release, e.g. "44.20261019.0"."""
    try:
        with open('/etc/os-release') as release:
            fields = dict(line.rstrip('\n').split('=', 1) for line in release if '=' in line)
    except OSError:
        return ''
    # VERSION="44.20261019.0 (Silverblue)"; VERSION_ID would only be "44"
    return fields.get('VERSION', '').strip('"').split(' (')[0]


class Updates(GObject.Object):
    """State: checking, current, available, installing, staged, failed or
    unknown. channel is "stable", "beta" or None (not known yet)."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.state = 'unknown'
        self.channel = None

    def check(self):
        self._set('checking')
        process = Gio.Subprocess.new([CHECK], Gio.SubprocessFlags.STDOUT_PIPE)
        process.communicate_utf8_async(None, None, self._on_checked)

    def _on_checked(self, process, result):
        try:
            _ok, stdout, _stderr = process.communicate_utf8_finish(result)
            lines = (stdout or '').split()
        except GLib.Error:
            lines = []
        for line in lines:
            if line.startswith('channel='):
                self.channel = line.split('=', 1)[1]
        state = lines[-1] if lines else 'unknown'
        self._set(state if state in ('current', 'available', 'staged') else 'unknown')

    def switch_channel(self, channel):
        """Stages the stable or beta image (asks for the admin password)."""
        self._set('installing')
        process = Gio.Subprocess.new(['pkexec', SWITCH_CHANNEL, channel], Gio.SubprocessFlags.NONE)
        process.wait_check_async(None, self._on_channel_switched, channel)

    def _on_channel_switched(self, process, result, channel):
        try:
            process.wait_check_finish(result)
            self.channel = channel
            self._set('staged')
        except GLib.Error:
            self._set('failed')

    def install(self):
        self._set('installing')
        process = Gio.Subprocess.new(['pkexec', INSTALL], Gio.SubprocessFlags.NONE)
        process.wait_check_async(None, self._on_installed)

    def _on_installed(self, process, result):
        try:
            process.wait_check_finish(result)
            self._set('staged')
        except GLib.Error:
            # Also when the password dialog was cancelled
            self._set('failed')

    def restart(self):
        Gio.Subprocess.new(['systemctl', 'reboot'], Gio.SubprocessFlags.NONE)

    def _set(self, state):
        self.state = state
        self.emit('changed')
