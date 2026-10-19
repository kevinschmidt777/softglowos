import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib

from .setup import SetupWindow, setup_done
from .window import HubWindow


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

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        if options.contains('setup-preview') or options.contains('setup'):
            preview = options.contains('setup-preview')
            if preview or not setup_done():
                SetupWindow(application=self, preview=preview).present()
            return 0
        self.activate()
        page = options.lookup_value('page', GLib.VariantType('s'))
        if page:
            self.props.active_window.show_page(page.get_string())
        return 0

    def do_activate(self):
        window = next((w for w in self.get_windows() if isinstance(w, HubWindow)), None)
        (window or HubWindow(application=self)).present()


def main():
    return HubApplication().run(sys.argv)
