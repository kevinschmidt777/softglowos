"""Installing Affinity from the Software page.

There's no Linux version, so the softglowos-affinity helper downloads the
AffinityOnLinux AppImage (Affinity with its own Wine) and adds a launcher.
It doesn't update itself: the Hub looks for a newer release once per start
and installs it over the old one on request."""

import os

from gi.repository import Gio, GLib, GObject

from . import software

HELPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'softglowos-affinity')


class Affinity(GObject.Object):
    """State of the Affinity row: missing, working (downloading, setting up
    or removing), installed or failed. update is the newer version, if any."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.state = 'installed' if software.is_installed(software.AFFINITY) else 'missing'
        self.step = None
        self.progress = 0
        self.update = None
        self._checked = False

    def check_update(self):
        """Asks GitHub once per Hub start whether there's a newer release."""
        if self._checked or self.state != 'installed':
            return
        self._checked = True
        process = Gio.Subprocess.new([HELPER, 'check'], Gio.SubprocessFlags.STDOUT_PIPE)
        process.communicate_utf8_async(None, None, self._on_checked)

    def _on_checked(self, process, result):
        try:
            _ok, stdout, _stderr = process.communicate_utf8_finish(result)
        except GLib.Error:
            return
        words = (stdout or '').split()
        self.update = words[1] if len(words) == 2 and words[0] == 'update' else None
        self.emit('changed')

    def install(self, _window=None):
        """Also updates: installs the newest release over the old one."""
        self._run('install')

    def remove(self):
        self._run('remove')

    def _run(self, action):
        process = Gio.Subprocess.new(
            [HELPER, action],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        stream = Gio.DataInputStream.new(process.get_stdout_pipe())
        self.step = 'remove' if action == 'remove' else 'download'
        self.progress = 0
        self._set('working')
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line, None)
        process.wait_check_async(None, self._on_done, action)

    def _on_line(self, stream, result, _data):
        line, _length = stream.read_line_finish_utf8(result)
        if line is None:
            return
        if line.startswith('@@step '):
            self.step = line.split()[1]
            self.emit('changed')
        elif line.startswith('@@progress '):
            self.progress = int(line.split()[1])
            self.emit('changed')
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line, None)

    def _on_done(self, process, result, action):
        try:
            process.wait_check_finish(result)
            ok = True
        except GLib.Error:
            ok = False
        self.step = None
        if action == 'remove':
            self._set('missing' if ok else 'installed')
        else:
            if ok:
                self.update = None
            was_installed = software.is_installed(software.AFFINITY)
            self._set('installed' if ok or was_installed else 'failed')

    def _set(self, state):
        self.state = state
        self.emit('changed')
