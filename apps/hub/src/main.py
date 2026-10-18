import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Adw, Gio

from .window import HubWindow


class HubApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id='com.softglowos.Hub',
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
            resource_base_path='/com/softglowos/Hub',
        )

    def do_activate(self):
        window = self.props.active_window or HubWindow(application=self)
        window.present()


def main():
    return HubApplication().run(sys.argv)
