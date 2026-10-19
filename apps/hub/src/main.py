import sys
import time
from pathlib import Path

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib

from .goxlr import Mixer
from .mini_mixer import MiniMixer
from .setup import SetupWindow, setup_done
from .tray import Tray
from .window import HubWindow

TRAY_AUTOSTART = 'com.softglowos.Hub.Tray.desktop'
TRAY_OVERRIDE = Path(GLib.get_user_config_dir()) / 'autostart' / TRAY_AUTOSTART


class HubApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id='com.softglowos.Hub',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
            resource_base_path='/com/softglowos/Hub',
        )
        self.add_main_option('page', 0, GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             'Page to open: mixer, devices, software or settings', 'PAGE')
        self.add_main_option('setup', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             'Run the setup assistant unless it was finished (autostart)', None)
        self.add_main_option('setup-preview', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             'Run the setup assistant without keeping or logging out', None)
        self.add_main_option('tray', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             'Show the mixer icon in the top bar and keep running (autostart)',
                             None)
        self._mixer = None
        self._tray = None
        self._mini_mixer = None
        self._mini_mixer_closed = 0

    @property
    def mixer(self):
        """One mixer connection for every window of this process."""
        if self._mixer is None:
            self._mixer = Mixer()
        return self._mixer

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        if options.contains('setup-preview') or options.contains('setup'):
            preview = options.contains('setup-preview')
            if preview or not setup_done():
                SetupWindow(application=self, preview=preview).present()
            # Both start with the session; whichever comes second hands its
            # command line to the first, which can time out while that one is
            # still building its window. So the setup brings the icon along.
            if options.contains('setup') and self.tray_enabled():
                self._start_tray()
            return 0
        if options.contains('tray'):
            if self.tray_enabled():
                self._start_tray()
            return 0
        self.activate()
        page = options.lookup_value('page', GLib.VariantType('s'))
        if page:
            self.props.active_window.show_page(page.get_string())
        return 0

    def do_activate(self):
        window = next((w for w in self.get_windows() if isinstance(w, HubWindow)), None)
        (window or HubWindow(application=self)).present()

    # Mixer icon in the top bar

    @staticmethod
    def tray_enabled():
        """Off when the user switched it off in the Hub (an autostart override)."""
        return not (TRAY_OVERRIDE.exists() and 'Hidden=true' in TRAY_OVERRIDE.read_text())

    def set_tray_enabled(self, enabled):
        if enabled:
            TRAY_OVERRIDE.unlink(missing_ok=True)
            self._start_tray()
        else:
            TRAY_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
            TRAY_OVERRIDE.write_text('[Desktop Entry]\nType=Application\nName=Mixer\n'
                                     'Hidden=true\n')
            self._stop_tray()

    def _start_tray(self):
        if self._tray is None:
            self._tray = Tray(self._toggle_mini_mixer, self.activate)
            self.hold()  # keeps running without windows

    def _stop_tray(self):
        if self._tray is not None:
            self._tray.stop()
            self._tray = None
            self.release()

    def _toggle_mini_mixer(self):
        if self._mini_mixer is not None:
            self._mini_mixer.close()
            return
        # A click on the icon while it's open first closes it (focus lost)
        if time.monotonic() - self._mini_mixer_closed < 0.3:
            return
        self._mini_mixer = MiniMixer(self.mixer, self.activate, application=self)
        self._mini_mixer.connect('close-request', self._on_mini_mixer_closed)
        self._mini_mixer.present()

    def _on_mini_mixer_closed(self, _window):
        self._mini_mixer = None
        self._mini_mixer_closed = time.monotonic()
        return False


def main():
    return HubApplication().run(sys.argv)
