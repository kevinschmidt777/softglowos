import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio, GLib

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

    def do_command_line(self, command_line):
        self.activate()
        page = command_line.get_options_dict().lookup_value('page', GLib.VariantType('s'))
        if page:
            self.props.active_window.show_page(page.get_string())
        return 0

    def do_activate(self):
        window = self.props.active_window or HubWindow(application=self)
        window.present()


def main():
    return HubApplication().run(sys.argv)
