from gi.repository import Adw, Gtk

from .bug_report import BugReportDialog
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


class SettingsPage(Adw.PreferencesPage):
    """System updates (checked here, installed only when the user says so),
    bug reports and the version."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
        self.add(group)

        help_group = Adw.PreferencesGroup(title=_('Help'))
        report = Adw.ActionRow(title=_('Report a bug'), activatable=True,
                               subtitle=_('Checks first whether it\'s already known'))
        report.add_suffix(Gtk.Image(icon_name='go-next-symbolic'))
        report.connect('activated', lambda _row: BugReportDialog().present(self))
        help_group.add(report)
        self.add(help_group)

        self.footer = Adw.PreferencesGroup()
        label = Gtk.Label(label=f'SoftglowOS {version()}'.strip())
        label.add_css_class('dim-label')
        self.footer.add(label)
        self.add(self.footer)

        self._show_updates()
        self.connect('map', self._on_map)

    def _on_map(self, _page):
        if self.updates.state == 'unknown':
            self.updates.check()

    def _show_updates(self):
        state = self.updates.state
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

    def _on_update_button(self, _button):
        state = self.updates.state
        if state in ('available', 'failed'):
            self.updates.install()
        elif state == 'staged':
            self._confirm_restart()
        else:
            self.updates.check()

    def _confirm_restart(self):
        dialog = Adw.AlertDialog(
            heading=_('Restart now?'),
            body=_('Open apps close. SoftglowOS starts with the new version.'))
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('restart', _('Restart'))
        dialog.set_response_appearance('restart', Adw.ResponseAppearance.SUGGESTED)
        dialog.connect('response', lambda _dialog, response:
                       response == 'restart' and self.updates.restart())
        dialog.present(self)
