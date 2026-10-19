from gi.repository import Adw, Gtk

from . import software
from .resolve import Resolve

RESOLVE_STEPS = {
    'unpack': _('Unpacking the installer …'),
    'container': _('Downloading the Resolve environment, this takes a while …'),
    'install': _('Installing …'),
    'remove': _('Removing …'),
}


def app_switches(group):
    """Adds a switch row for every installed curated app to a group (also
    used by the setup assistant)."""
    for app in software.APPS:
        if not software.is_installed(app):
            continue
        row = Adw.SwitchRow(title=app.name, subtitle=app.detail,
                            active=software.is_shown(app))
        row.connect('notify::active', lambda r, _param, a=app: software.set_shown(a, r.get_active()))
        group.add(row)


class SoftwarePage(Adw.PreferencesPage):
    """Curated creator apps with a switch each, DaVinci Resolve to install
    on demand, and a way into Bazaar for everything else."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        apps = Adw.PreferencesGroup(title=_('Ready for creators'))
        app_switches(apps)

        self.resolve = Resolve()
        self.resolve.connect('changed', lambda _resolve: self._show_resolve())
        self.resolve_row = Adw.ActionRow(title=software.RESOLVE.name)
        self.resolve_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.resolve_switch.update_property([Gtk.AccessibleProperty.LABEL],
                                            [software.RESOLVE.name])
        self.resolve_switch.connect('notify::active', self._on_resolve_switch)
        self.resolve_remove = Gtk.Button(label=_('Remove'), valign=Gtk.Align.CENTER)
        self.resolve_remove.add_css_class('flat')
        self.resolve_remove.connect('clicked', self._on_resolve_remove)
        self.resolve_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.resolve_button.connect('clicked', self._on_resolve_button)
        self.resolve_spinner = Adw.Spinner()
        for widget in (self.resolve_spinner, self.resolve_remove,
                       self.resolve_switch, self.resolve_button):
            self.resolve_row.add_suffix(widget)
        apps.add(self.resolve_row)
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

        self._show_resolve()

    def _show_resolve(self):
        state = self.resolve.state
        self.resolve_spinner.set_visible(state in ('waiting', 'working'))
        self.resolve_switch.set_visible(state == 'installed')
        self.resolve_remove.set_visible(state == 'installed')
        self.resolve_button.set_visible(state in ('missing', 'waiting', 'failed'))

        if state == 'installed':
            self.resolve_row.set_subtitle(software.RESOLVE.detail)
            self._updating = True
            self.resolve_switch.set_active(software.is_shown(software.RESOLVE))
            self._updating = False
        elif state == 'waiting':
            self.resolve_row.set_subtitle(
                _('Download DaVinci Resolve for Linux in your browser, the Hub takes over from there'))
            self.resolve_button.set_label(_('Cancel'))
        elif state == 'working':
            self.resolve_row.set_subtitle(RESOLVE_STEPS.get(self.resolve.step, ''))
        elif state == 'failed':
            self.resolve_row.set_subtitle(_('The installation didn\'t work. Try again.'))
            self.resolve_button.set_label(_('Try again'))
        else:
            self.resolve_row.set_subtitle(
                _('Video editing, downloads the official installer from Blackmagic'))
            self.resolve_button.set_label(_('Install'))

    def _on_resolve_button(self, _button):
        if self.resolve.state == 'waiting':
            self.resolve.cancel()
        else:
            self.resolve.install(self.get_root())

    def _on_resolve_switch(self, switch, _param):
        if not getattr(self, '_updating', False):
            software.set_shown(software.RESOLVE, switch.get_active())

    def _on_resolve_remove(self, _button):
        dialog = Adw.AlertDialog(
            heading=_('Remove DaVinci Resolve?'),
            body=_('Resolve and its environment are deleted. Your projects and media stay.'))
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('remove', _('Remove'))
        dialog.set_response_appearance('remove', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', lambda _dialog, response:
                       response == 'remove' and self.resolve.remove())
        dialog.present(self)
