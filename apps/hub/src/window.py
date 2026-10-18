from gi.repository import Adw, Gtk

from .goxlr import Mixer
from .mixer_page import MixerPage


def coming_soon(icon_name):
    return Adw.StatusPage(
        icon_name=icon_name,
        title=_('Coming soon'),
        description=_('This area is still being built.'),
    )


@Gtk.Template(resource_path='/com/softglowos/Hub/window.ui')
class HubWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'HubWindow'

    split_view = Gtk.Template.Child()
    sidebar_list = Gtk.Template.Child()
    content_page = Gtk.Template.Child()
    stack = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        pages = (
            ('mixer', _('Mixer'), 'multimedia-volume-control-symbolic',
             MixerPage(Mixer())),
            ('devices', _('Devices'), 'preferences-system-devices-symbolic',
             coming_soon('preferences-system-devices-symbolic')),
            ('software', _('Software'), 'preferences-desktop-apps-symbolic',
             coming_soon('preferences-desktop-apps-symbolic')),
            ('settings', _('Settings'), 'emblem-system-symbolic',
             coming_soon('emblem-system-symbolic')),
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

    @Gtk.Template.Callback()
    def on_row_selected(self, _list, row):
        if row is None:
            return
        page_id = row.get_name()
        self.stack.set_visible_child_name(page_id)
        self.content_page.set_title(self._titles[page_id])
        self.split_view.set_show_content(True)
