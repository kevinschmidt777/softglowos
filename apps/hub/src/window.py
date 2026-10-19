from gi.repository import Adw, Gtk

from .devices_page import DevicesPage
from .goxlr import Mixer
from .mixer_page import MixerPage
from .settings_page import SettingsPage
from .software_page import SoftwarePage


@Gtk.Template(resource_path='/com/softglowos/Hub/window.ui')
class HubWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'HubWindow'

    split_view = Gtk.Template.Child()
    sidebar_list = Gtk.Template.Child()
    content_page = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        mixer = Mixer()
        self.mixer_page = MixerPage(mixer)
        pages = (
            ('mixer', _('Mixer'), 'multimedia-volume-control-symbolic',
             self.mixer_page),
            ('devices', _('Devices'), 'preferences-system-devices-symbolic',
             DevicesPage(mixer, self._open_in_mixer)),
            ('software', _('Software'), 'preferences-desktop-apps-symbolic',
             SoftwarePage()),
            ('settings', _('Settings'), 'emblem-system-symbolic',
             SettingsPage()),
        )

        self._titles = {}
        for page_id, title, icon_name, widget in pages:
            box = Gtk.Box(spacing=12)
            box.append(Gtk.Image(icon_name=icon_name))
            box.append(Gtk.Label(label=title, xalign=0))
            self.sidebar_list.append(Gtk.ListBoxRow(name=page_id, child=box))
            self.stack.add_named(widget, page_id)
            self._titles[page_id] = title

        self.sidebar_list.select_row(self.sidebar_list.get_row_at_index(0))

    def show_page(self, page_id):
        row = self.sidebar_list.get_first_child()
        while row and row.get_name() != page_id:
            row = row.get_next_sibling()
        if row:
            self.sidebar_list.select_row(row)

    def _open_in_mixer(self, picker=None):
        """Shows the mixer, with one of its device pickers opened."""
        self.show_page('mixer')
        if picker:
            self.mixer_page.open_picker(picker)

    @Gtk.Template.Callback()
    def on_row_selected(self, _list, row):
        if row is None:
            return
        page_id = row.get_name()
        self.stack.set_visible_child_name(page_id)
        self.content_page.set_title(self._titles[page_id])
        self.split_view.set_show_content(True)
