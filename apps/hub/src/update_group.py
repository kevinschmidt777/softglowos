import subprocess
import threading

from gi.repository import Adw, GLib, Gtk

from . import updates


class UpdateGroup(Adw.PreferencesGroup):
    """Settings → Updates: whether a new SoftglowOS version is there, what it
    brings (CHANGELOG.md) and a button to install it now. Updates otherwise
    come on their own in the background (unattended-upgrades)."""

    def __init__(self, **kwargs):
        super().__init__(title=_('Updates'), **kwargs)
        self._available = ''
        self._busy = False

        self.status = Adw.ActionRow(title=_('Checking for updates …'))
        self.status.set_subtitle_lines(2)
        self.spinner = Adw.Spinner(visible=False)
        self.status.add_suffix(self.spinner)
        self.button = Gtk.Button(valign=Gtk.Align.CENTER)
        self.button.connect('clicked', self._on_button)
        self.status.add_suffix(self.button)
        self.add(self.status)

        self.notes = Adw.ExpanderRow(visible=False)
        self.add(self.notes)
        self._note_rows = []

        self.refresh()

    # States

    def refresh(self):
        """Compares the installed version with the one apt offers."""
        self._set_busy(True)
        self.status.set_title(_('Checking for updates …'))
        self.status.set_subtitle('')

        def work():
            available = updates.update_available()
            GLib.idle_add(self._show_result, available)
        threading.Thread(target=work, daemon=True).start()

    def _show_result(self, available):
        self._set_busy(False)
        self._available = available
        installed = updates.installed_version()
        if available:
            self.status.set_title(_('SoftglowOS {version} is available').format(version=available))
            self.status.set_subtitle(_('Installed: {version}').format(version=installed))
            self._set_button(_('Update now'), suggested=True)
            self.notes.set_title(_('What\'s new'))
            self.notes.set_expanded(True)
            self._show_notes(updates.local_changelog(), installed, available)
            updates.fetch_changelog(
                lambda changelog: self._show_notes(changelog, installed, available)
                if changelog else None)
        else:
            self.status.set_title(_('SoftglowOS is up to date'))
            self.status.set_subtitle(
                _('Version {version} · New versions install themselves in the background')
                .format(version=installed) if installed else
                _('New versions install themselves in the background'))
            self._set_button(_('Check for updates'))
            self.notes.set_title(_('What\'s new in {version}').format(version=installed))
            self.notes.set_expanded(False)
            self._show_notes(updates.local_changelog(), _previous(installed), installed)
        return GLib.SOURCE_REMOVE

    def _show_notes(self, changelog, old, new):
        for row in self._note_rows:
            self.notes.remove(row)
        self._note_rows = []
        for number, sections in updates.notes_between(changelog, old, new):
            for heading, entries in sections:
                title = heading if number == new else f'{number} · {heading}'
                label = Gtk.Label(label=title, xalign=0, margin_top=12, margin_start=12,
                                  margin_end=12)
                label.add_css_class('heading')
                self._add_note(label)
                for entry in entries:
                    self._add_note(Gtk.Label(label=f'•  {entry}', xalign=0, wrap=True,
                                             margin_top=4, margin_bottom=4, margin_start=12,
                                             margin_end=12))
        self.notes.set_visible(bool(self._note_rows))

    def _add_note(self, widget):
        row = Gtk.ListBoxRow(child=widget, activatable=False, selectable=False)
        self.notes.add_row(row)
        self._note_rows.append(row)

    # Actions

    def _on_button(self, _button):
        if self._busy:
            return
        if self.button.action == 'reboot':
            subprocess.Popen(['gnome-session-quit', '--reboot'])
        elif self.button.action == 'update':
            self._update()
        else:
            self._check()

    def _check(self):
        self._set_busy(True)
        self.status.set_title(_('Checking for updates …'))
        self.status.set_subtitle('')
        updates.run_helper('check', lambda _ok, _output: self.refresh())

    def _update(self):
        new = self._available
        self._set_busy(True)
        self.status.set_title(_('Updating to SoftglowOS {version} …').format(version=new))
        self.status.set_subtitle(_('This can take a few minutes'))

        def done(ok, output):
            self._set_busy(False)
            if ok:
                self.status.set_title(_('SoftglowOS {version} is installed')
                                      .format(version=updates.installed_version() or new))
                self.status.set_subtitle(_('Restart the computer so everything takes effect'))
                self._set_button(_('Restart'), action='reboot', suggested=True)
                self.notes.set_title(_('What\'s new'))
            else:
                self.status.set_title(_('The update didn\'t work'))
                last = [line for line in output.splitlines() if line.strip()]
                self.status.set_subtitle(GLib.markup_escape_text(last[-1]) if last else '')
                self._set_button(_('Try again'), action='update', suggested=True)

        updates.run_helper('upgrade', done,
                           lambda line: self.status.set_subtitle(GLib.markup_escape_text(line)))

    def _set_button(self, label, action=None, suggested=False):
        self.button.set_label(label)
        self.button.action = action or ('update' if suggested else 'check')
        if suggested:
            self.button.add_css_class('suggested-action')
        else:
            self.button.remove_css_class('suggested-action')

    def _set_busy(self, busy):
        self._busy = busy
        self.spinner.set_visible(busy)
        self.button.set_visible(not busy)


def _previous(number):
    """The version right before, for "what's new in" the installed one:
    1.0.1 -> 1.0.0, 1.1.0 -> 1.0.999, 2.0.0 -> 1.999.999."""
    parts = [int(part) if part.isdigit() else 0 for part in number.split('.')] if number else []
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] > 0:
            parts[index] -= 1
            return '.'.join(str(part) for part in parts[:index + 1] +
                            [999] * (len(parts) - index - 1))
    return ''
