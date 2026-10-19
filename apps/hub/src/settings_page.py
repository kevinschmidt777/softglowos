from gi.repository import Adw, Gio, Gtk

from . import crash_reports
from .bug_report import BugReportDialog
from .gpu import GraphicsDriver
from .updates import Updates, version

# State -> (description, button label or None); see Updates
UPDATE_STATES = {
    'checking': (_('Looking for updates …'), None),
    'current': (_('SoftglowOS is up to date'), _('Check for updates')),
    'available': (_('A new version is out'), _('Install update')),
    'installing': (_('Installing, this takes a few minutes …'), None),
    'staged': (_('Installed, active after a restart'), _('Restart')),
    'failed': (_('The update didn\'t work'), _('Try again')),
    'unknown': (_('Couldn\'t look for updates'), _('Check for updates')),
}

# State -> (description, button label or None); see GraphicsDriver
DRIVER_STATES = {
    'checking': (_('Looking at the graphics card …'), None),
    'fits-amd': (_('Set up for AMD and Intel graphics'), None),
    'fits-nvidia': (_('NVIDIA driver set up'), None),
    'old-nvidia': (_('Free driver: the NVIDIA driver supports RTX 20 / GTX 16 and newer'), None),
    'nvidia': (_('NVIDIA graphics card found, its driver isn\'t set up yet'), _('Set up')),
    'amd': (_('The driver doesn\'t fit your graphics card anymore'), _('Set up')),
    'switching': (_('Setting up, this takes a few minutes …'), None),
    'staged': (_('Set up, active after a restart'), _('Restart')),
    'failed': (_('Setting up the driver didn\'t work'), _('Try again')),
    'unknown': (_('Couldn\'t look at the graphics card'), None),
}


class SettingsPage(Adw.PreferencesPage):
    """Graphics driver, system updates (checked here, installed only when the
    user says so), bug reports and the version."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.driver = GraphicsDriver()
        self.driver.connect('changed', lambda _driver: self._show_driver())

        driver_group = Adw.PreferencesGroup(title=_('Graphics'))
        self.driver_row = Adw.ActionRow(title=_('Graphics driver'))
        self.driver_spinner = Adw.Spinner()
        self.driver_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.driver_button.add_css_class('suggested-action')
        self.driver_button.connect('clicked', self._on_driver_button)
        self.driver_row.add_suffix(self.driver_spinner)
        self.driver_row.add_suffix(self.driver_button)
        driver_group.add(self.driver_row)
        self.add(driver_group)

        mixer_group = Adw.PreferencesGroup(title=_('Mixer'))
        tray = Adw.SwitchRow(title=_('Mixer in the top bar'),
                             subtitle=_('An icon for quick access, starts with your login'),
                             active=Gio.Application.get_default().tray_enabled())
        tray.connect('notify::active', lambda row, _param:
                     Gio.Application.get_default().set_tray_enabled(row.get_active()))
        mixer_group.add(tray)
        self.add(mixer_group)

        self.updates = Updates()
        self.updates.connect('changed', lambda _updates: self._show_updates())

        group = Adw.PreferencesGroup(title=_('Updates'))
        self.update_row = Adw.ActionRow(title=_('System updates'))
        self.update_spinner = Adw.Spinner()
        self.update_button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.update_button.connect('clicked', self._on_update_button)
        self.update_row.add_suffix(self.update_spinner)
        self.update_row.add_suffix(self.update_button)
        group.add(self.update_row)
        self.beta_row = Adw.SwitchRow(title=_('Get beta versions'),
                                      subtitle=_('New features earlier, may contain bugs'),
                                      sensitive=False)
        self._beta_handler = self.beta_row.connect('notify::active', self._on_beta_toggled)
        group.add(self.beta_row)
        self.add(group)

        help_group = Adw.PreferencesGroup(title=_('Help'))
        report = Adw.ActionRow(title=_('Report a bug'), activatable=True,
                               subtitle=_('Checks first whether it\'s already known'))
        report.add_suffix(Gtk.Image(icon_name='go-next-symbolic'))
        report.connect('activated', lambda _row: BugReportDialog().present(self))
        help_group.add(report)
        crashes = Adw.SwitchRow(title=_('Send crash reports'),
                                subtitle=_('Helps find bugs. Nothing personal, deleted after a year.'),
                                active=crash_reports.enabled())
        crashes.connect('notify::active', lambda row, _p: crash_reports.set_enabled(row.get_active()))
        help_group.add(crashes)
        self.add(help_group)

        self.footer = Adw.PreferencesGroup()
        number, build = version()
        label = Gtk.Label(label=f'SoftglowOS {number}'.strip() + (f' · Build {build}' if build else ''))
        label.add_css_class('dim-label')
        self.footer.add(label)
        self.add(self.footer)

        self._show_driver()
        self._show_updates()
        self.connect('map', self._on_map)

    def _on_map(self, _page):
        if self.driver.state in ('unknown', 'fits-amd', 'fits-nvidia', 'old-nvidia', 'nvidia', 'amd'):
            self.driver.check()
        if self.updates.state == 'unknown':
            self.updates.check()

    def _show_driver(self):
        state = self.driver.state
        text, button = DRIVER_STATES[state]
        self.driver_row.set_subtitle(text)
        self.driver_spinner.set_visible(state in ('checking', 'switching'))
        self.driver_button.set_visible(button is not None)
        if button:
            self.driver_button.set_label(button)

    def _on_driver_button(self, _button):
        if self.driver.state == 'staged':
            self._confirm_restart(_('SoftglowOS starts with the new graphics driver.'),
                                  self.driver.restart)
        else:
            self.driver.switch()

    def _show_updates(self):
        state = self.updates.state
        channel = self.updates.channel
        with self.beta_row.handler_block(self._beta_handler):
            self.beta_row.set_active(channel == 'beta')
        self.beta_row.set_sensitive(channel is not None and state not in ('checking', 'installing'))
        text, button = UPDATE_STATES[state]
        self.update_row.set_subtitle(text)
        self.update_spinner.set_visible(state in ('checking', 'installing'))
        self.update_button.set_visible(button is not None)
        if button:
            self.update_button.set_label(button)
        if state in ('available', 'staged'):
            self.update_button.add_css_class('suggested-action')
        else:
            self.update_button.remove_css_class('suggested-action')

    def _on_beta_toggled(self, row, _param):
        beta = row.get_active()
        dialog = Adw.AlertDialog(
            heading=_('Switch to beta versions?') if beta else _('Back to stable versions?'),
            body=(_('You get new features earlier, they may contain bugs. Settings, apps and '
                    'files stay. Active after a restart.') if beta else
                  _('The next stable version replaces the beta. Settings, apps and files stay. '
                    'Active after a restart.')))
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('switch', _('Switch'))
        dialog.set_response_appearance('switch', Adw.ResponseAppearance.SUGGESTED)

        def on_response(_dialog, response):
            if response == 'switch':
                self.updates.switch_channel('beta' if beta else 'stable')
            else:
                self._show_updates()  # puts the switch back

        dialog.connect('response', on_response)
        dialog.present(self)

    def _on_update_button(self, _button):
        state = self.updates.state
        if state in ('available', 'failed'):
            self.updates.install()
        elif state == 'staged':
            self._confirm_restart(_('SoftglowOS starts with the new version.'),
                                  self.updates.restart)
        else:
            self.updates.check()

    def _confirm_restart(self, reason, restart):
        dialog = Adw.AlertDialog(
            heading=_('Restart now?'),
            body=_('Open apps close.') + ' ' + reason)
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('restart', _('Restart'))
        dialog.set_response_appearance('restart', Adw.ResponseAppearance.SUGGESTED)
        dialog.connect('response', lambda _dialog, response:
                       response == 'restart' and restart())
        dialog.present(self)
