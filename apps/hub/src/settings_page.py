from gi.repository import Adw, Gio, Gtk

from . import crash_reports
from .bug_report import BugReportDialog
from .version import version


class SettingsPage(Adw.PreferencesPage):
    """Mixer in the top bar, bug reports, crash reports and the version.
    System updates come through apt like every other package."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        mixer_group = Adw.PreferencesGroup(title=_('Mixer'))
        tray = Adw.SwitchRow(title=_('Mixer in the top bar'),
                             subtitle=_('An icon for quick access, starts with your login'),
                             active=Gio.Application.get_default().tray_enabled())
        tray.connect('notify::active', lambda row, _param:
                     Gio.Application.get_default().set_tray_enabled(row.get_active()))
        mixer_group.add(tray)
        self.add(mixer_group)

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
