"""Installing DaVinci Resolve from the Software page.

Blackmagic only hands out the installer after its registration form, so the
Hub opens the download page and waits for the ZIP in the download folder.
As soon as it's there, the softglowos-resolve helper sets Resolve up in a
davincibox container."""

import os
import re
from pathlib import Path

from gi.repository import Gio, GLib, GObject, Gtk

from . import software

DOWNLOAD_PAGE = 'https://www.blackmagicdesign.com/event/davinciresolvedownload'
# Only the free version; Studio needs a license key we can't enter for the user
INSTALLER = re.compile(r'^DaVinci_Resolve_\d[\d.]*_Linux\.zip$')
HELPER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'softglowos-resolve')


class Resolve(GObject.Object):
    """State of the Resolve row: missing, waiting (for the download),
    working (installing or removing), installed or failed."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.state = 'installed' if software.is_installed(software.RESOLVE) else 'missing'
        self.step = None
        self._monitor = None
        self._downloads = Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                               or GLib.get_home_dir())

    def install(self, window):
        """Uses a ZIP that's already downloaded, else opens the download page
        and waits for one."""
        found = sorted(path for path in self._downloads.iterdir()
                       if INSTALLER.match(path.name))
        if found:
            self._run('install', str(found[-1]))
            return
        self._monitor = Gio.File.new_for_path(str(self._downloads)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.connect('changed', self._on_download_changed)
        Gtk.UriLauncher.new(DOWNLOAD_PAGE).launch(window, None, None)
        self._set('waiting')

    def cancel(self):
        self._stop_watching()
        self._set('missing')

    def remove(self):
        self._run('remove')

    def _on_download_changed(self, _monitor, file, other_file, event):
        # Browsers download into a temporary name and rename it at the end;
        # some write the final name directly.
        if event == Gio.FileMonitorEvent.RENAMED:
            file = other_file
        elif event not in (Gio.FileMonitorEvent.MOVED_IN,
                           Gio.FileMonitorEvent.CHANGES_DONE_HINT):
            return
        if file and INSTALLER.match(file.get_basename()):
            self._stop_watching()
            self._run('install', file.get_path())

    def _stop_watching(self):
        if self._monitor:
            self._monitor.cancel()
            self._monitor = None

    def _run(self, *args):
        process = Gio.Subprocess.new(
            [HELPER, *args],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        stream = Gio.DataInputStream.new(process.get_stdout_pipe())
        self.step = 'remove' if args[0] == 'remove' else 'unpack'
        self._set('working')
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_line, None)
        process.wait_check_async(None, self._on_done, args[0])

    def _on_line(self, stream, result, _data):
        line, _length = stream.read_line_finish_utf8(result)
        if line is None:
            return
        if line.startswith('@@step '):
            self.step = line.split()[1]
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
            self._set('installed' if ok else 'failed')

    def _set(self, state):
        self.state = state
        self.emit('changed')
