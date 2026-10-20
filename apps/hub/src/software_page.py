from gi.repository import Adw, Gtk

from . import software
from .affinity import Affinity
from .resolve import Resolve


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


class OnDemandRow(Adw.ActionRow):
    """An app the Hub installs on request (Resolve, Affinity): Install,
    progress, then a show/hide switch, Remove and, if offered, Update.
    The installer has a state (missing, waiting, working, installed or
    failed), the current step and a "changed" signal; see resolve.py."""

    def __init__(self, app, installer, texts, **kwargs):
        super().__init__(title=app.name, **kwargs)
        self.app = app
        self.installer = installer
        self.texts = texts
        self._updating = False

        self.spinner = Adw.Spinner()
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.update_property([Gtk.AccessibleProperty.LABEL], [app.name])
        self.switch.connect('notify::active', self._on_switch)
        self.remove_button = Gtk.Button(label=_('Remove'), valign=Gtk.Align.CENTER)
        self.remove_button.add_css_class('flat')
        self.remove_button.connect('clicked', self._on_remove)
        self.button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.button.connect('clicked', self._on_button)
        for widget in (self.spinner, self.remove_button, self.button, self.switch):
            self.add_suffix(widget)

        installer.connect('changed', lambda _installer: self._show())
        self._show()

    def _show(self):
        state = self.installer.state
        update = getattr(self.installer, 'update', None) if state == 'installed' else None
        self.spinner.set_visible(state in ('waiting', 'working'))
        self.switch.set_visible(state == 'installed')
        self.remove_button.set_visible(state == 'installed')
        self.button.set_visible(state in ('missing', 'waiting', 'failed') or update is not None)

        if update:
            self.set_subtitle(_('Version {version} is out').format(version=update))
            self.button.set_label(_('Update'))
        elif state == 'installed':
            self.set_subtitle(self.app.detail)
        elif state == 'waiting':
            self.set_subtitle(self.texts['waiting'])
            self.button.set_label(_('Cancel'))
        elif state == 'working':
            step = self.installer.step
            text = self.texts['steps'].get(step, '')
            if step == 'download':
                text = text.format(percent=getattr(self.installer, 'progress', 0))
            self.set_subtitle(text)
        elif state == 'failed':
            self.set_subtitle(_('The installation didn\'t work. Try again.'))
            self.button.set_label(_('Try again'))
        else:
            self.set_subtitle(self.texts['missing'])
            self.button.set_label(_('Install'))
        if state == 'installed':
            self._updating = True
            self.switch.set_active(software.is_shown(self.app))
            self._updating = False

    def _on_button(self, _button):
        if self.installer.state == 'waiting':
            self.installer.cancel()
        else:
            self.installer.install(self.get_root())

    def _on_switch(self, switch, _param):
        if not self._updating:
            software.set_shown(self.app, switch.get_active())

    def _on_remove(self, _button):
        dialog = Adw.AlertDialog(
            heading=_('Remove {app}?').format(app=self.app.name),
            body=self.texts['remove'])
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('remove', _('Remove'))
        dialog.set_response_appearance('remove', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', lambda _dialog, response:
                       response == 'remove' and self.installer.remove())
        dialog.present(self.get_root())


class SoftwarePage(Adw.PreferencesPage):
    """Curated creator apps with a switch each, DaVinci Resolve and Affinity
    to install on demand, and a way into Bazaar for everything else."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        apps = Adw.PreferencesGroup(title=_('Ready for creators'))
        self.rows = app_switches(apps)

        apps.add(OnDemandRow(software.RESOLVE, Resolve(), {
            'missing': _('Video editing, downloads the official installer from Blackmagic'),
            'waiting': _('Download DaVinci Resolve for Linux in your browser, '
                         'the Hub takes over from there'),
            'steps': {
                'unpack': _('Unpacking the installer …'),
                'container': _('Downloading the Resolve environment, this takes a while …'),
                'install': _('Installing …'),
                'remove': _('Removing …'),
            },
            'remove': _('Resolve and its environment are deleted. Your projects and media stay.'),
        }))

        self.affinity = Affinity()
        apps.add(OnDemandRow(software.AFFINITY, self.affinity, {
            'missing': _('Photo, design and layout, runs the Windows version through '
                         'the community project AffinityOnLinux'),
            'steps': {
                'download': _('Downloading, {percent} % …'),
                'setup': _('Setting up …'),
                'remove': _('Removing …'),
            },
            'remove': _('Affinity is deleted. Your documents stay.'),
        }))
        self.add(apps)
        self.connect('map', lambda _page: self.affinity.check_update())

        more = Adw.PreferencesGroup()
        store_row = Adw.ActionRow(title=_('More apps'),
                                  subtitle=_('Thousands of apps from Flathub in the app store'))
        store_button = Gtk.Button(label=_('Open app store'), valign=Gtk.Align.CENTER)
        store_button.connect('clicked', lambda _button: software.open_store())
        store_row.add_suffix(store_button)
        more.add(store_row)
        more.set_visible(software.is_installed(software.App('store', '', '', (software.STORE_ID,))))
        self.add(more)
