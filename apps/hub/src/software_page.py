from gi.repository import Adw, Gtk

from . import software


def app_switches(group):
    """Adds a switch row for every installed curated app to a group (also
    used by the setup assistant). Returns the rows by app id."""
    rows = {}
    for app in software.APPS:
        if not software.is_installed(app):
            continue
        row = Adw.SwitchRow(title=app.name, subtitle=app.detail,
                            active=software.is_shown(app))
        row.connect('notify::active', lambda r, _param, a=app: software.set_shown(a, r.get_active()))
        group.add(row)
        rows[app.id] = row
    return rows


class SoftwarePage(Adw.PreferencesPage):
    """Curated creator apps with a switch each and a way into the app store
    for everything else."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        apps = Adw.PreferencesGroup(title=_('Ready for creators'))
        self.rows = app_switches(apps)
        self.add(apps)

        more = Adw.PreferencesGroup()
        store_row = Adw.ActionRow(title=_('More apps'),
                                  subtitle=_('Thousands of apps from Flathub in the app store'))
        store_button = Gtk.Button(label=_('Open app store'), valign=Gtk.Align.CENTER)
        store_button.connect('clicked', lambda _button: software.open_store())
        store_row.add_suffix(store_button)
        more.add(store_row)
        more.set_visible(software.is_installed(software.App('store', '', '', (software.STORE_ID,))))
        self.add(more)
