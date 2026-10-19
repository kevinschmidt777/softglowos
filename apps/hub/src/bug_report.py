"""Reporting a bug as a GitHub issue.

While the user types a title, the dialog searches the existing issues, so a
known bug gets found before it's reported twice. "Send" posts title,
description and the system details shown in the dialog to softglowos.com,
which opens the issue with a bot account, so no GitHub account is needed.
If that fails (offline, too many reports), the user can still open a
prefilled issue on GitHub."""

import json
import os
import subprocess
from urllib.parse import quote, urlencode

import gi

gi.require_version('Soup', '3.0')

from gi.repository import Adw, Gio, GLib, Gtk, Soup

from .updates import version

REPO = 'kevinschmidt777/softglowos'
RELAY = os.environ.get('SOFTGLOWOS_BUG_URL', 'https://softglowos.com/api/bug')
MIN_TITLE = 5  # the relay wants at least this many characters
SEARCH_DELAY_MS = 600


def system_details():
    lines = [f'- SoftglowOS {version()}', f'- Kernel {os.uname().release}']
    try:
        lspci = subprocess.run(['lspci'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        lspci = ''
    for line in lspci.splitlines():
        if ' VGA ' in line or ' 3D ' in line:
            lines.append(f'- GPU: {line.split(": ", 1)[-1]}')
    return '\n'.join(lines)


class BugReportDialog(Adw.Dialog):
    def __init__(self):
        super().__init__(title=_('Report a bug'), content_width=560, content_height=640)
        # GitHub's API turns away requests without a User-Agent
        self._session = Soup.Session(user_agent='SoftglowOS-Hub')
        self._search_source = 0
        self._cancellable = None

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())

        page = Adw.PreferencesPage()
        form = Adw.PreferencesGroup(
            description=_('Bugs are collected publicly on GitHub, no account needed. '
                          'Please don\'t write anything personal.'))
        self.title_row = Adw.EntryRow(title=_('What went wrong, in one sentence'))
        self.title_row.connect('changed', self._on_title_changed)
        form.add(self.title_row)
        page.add(form)

        details = Adw.PreferencesGroup(title=_('Details'))
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, height_request=140,
                                 top_margin=12, bottom_margin=12,
                                 left_margin=12, right_margin=12)
        self.text.update_property([Gtk.AccessibleProperty.LABEL], [_('Details')])
        frame = Gtk.Frame(child=self.text)
        frame.add_css_class('card')
        details.add(frame)
        hint = Gtk.Label(label=_('What did you do, what happened, what did you expect?'),
                         xalign=0, wrap=True, margin_top=6)
        hint.add_css_class('caption')
        hint.add_css_class('dim-label')
        details.add(hint)
        page.add(details)

        self.details = system_details()
        sent = Adw.PreferencesGroup(title=_('Sent along'))
        sent_label = Gtk.Label(label=self.details, xalign=0, wrap=True, selectable=True)
        sent_label.add_css_class('caption')
        sent_label.add_css_class('dim-label')
        sent.add(sent_label)
        page.add(sent)

        self.matches = Adw.PreferencesGroup(
            title=_('Already reported?'),
            description=_('If your bug is in here, add to it instead of reporting it again.'),
            visible=False)
        self._match_rows = []
        page.add(self.matches)

        toolbar.set_content(page)
        self.send_button = Gtk.Button(label=_('Send'), sensitive=False,
                                      halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=18)
        self.send_button.add_css_class('suggested-action')
        self.send_button.connect('clicked', self._on_send)
        toolbar.add_bottom_bar(self.send_button)
        self.stack = Gtk.Stack()
        self.stack.add_named(toolbar, 'form')
        self.set_child(self.stack)

    def _on_title_changed(self, row):
        self.send_button.set_sensitive(len(row.get_text().strip()) >= MIN_TITLE)
        if self._search_source:
            GLib.source_remove(self._search_source)
        self._search_source = GLib.timeout_add(SEARCH_DELAY_MS, self._search)

    def _search(self):
        self._search_source = 0
        if self._cancellable:
            self._cancellable.cancel()
        words = self.title_row.get_text().strip()
        if len(words) < 3:
            self._show_matches([])
            return GLib.SOURCE_REMOVE
        query = urlencode({'q': f'{words} repo:{REPO} is:issue', 'per_page': 5})
        message = Soup.Message.new('GET', f'https://api.github.com/search/issues?{query}')
        message.get_request_headers().append('Accept', 'application/vnd.github+json')
        self._cancellable = Gio.Cancellable()
        self._session.send_and_read_async(message, GLib.PRIORITY_DEFAULT,
                                          self._cancellable, self._on_results, None)
        return GLib.SOURCE_REMOVE

    def _on_results(self, session, result, _data):
        try:
            data = json.loads(session.send_and_read_finish(result).get_data())
        except (GLib.Error, ValueError):
            # Offline or rate-limited: the user can still report
            return
        self._show_matches(data.get('items', []))

    def _show_matches(self, issues):
        for row in self._match_rows:
            self.matches.remove(row)
        self._match_rows = []
        for issue in issues:
            state = _('open') if issue.get('state') == 'open' else _('closed')
            row = Adw.ActionRow(title=GLib.markup_escape_text(issue.get('title', '')),
                                subtitle=f'#{issue.get("number")} · {state}',
                                activatable=True)
            row.add_suffix(Gtk.Image(icon_name='adw-external-link-symbolic'))
            row.connect('activated', lambda _row, url=issue.get('html_url'): self._open(url))
            self.matches.add(row)
            self._match_rows.append(row)
        self.matches.set_visible(bool(issues))

    def _texts(self):
        buffer = self.text.get_buffer()
        description = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False).strip()
        return self.title_row.get_text().strip(), description

    def _on_send(self, _button):
        title, description = self._texts()
        self.send_button.set_sensitive(False)
        self.send_button.set_label(_('Sending …'))
        message = Soup.Message.new('POST', RELAY)
        body = json.dumps({'title': title, 'description': description[:5000],
                           'details': self.details[:2000]}).encode()
        message.set_request_body_from_bytes('application/json', GLib.Bytes.new(body))
        self._session.send_and_read_async(message, GLib.PRIORITY_DEFAULT, None,
                                          self._on_sent, message)

    def _on_sent(self, session, result, message):
        try:
            data = json.loads(session.send_and_read_finish(result).get_data())
            ok = message.get_status() == 201
        except (GLib.Error, ValueError):
            data, ok = {}, False
        if ok:
            self._show_thanks(data.get('number'), data.get('url'))
            return
        self.send_button.set_label(_('Send'))
        self.send_button.set_sensitive(True)
        dialog = Adw.AlertDialog(
            heading=_('Couldn\'t send the report'),
            body=_('Maybe you\'re offline or sent several reports in a short time. '
                   'You can try again later or report it on GitHub instead (needs an account).'))
        dialog.add_response('cancel', _('Cancel'))
        dialog.add_response('github', _('Report on GitHub'))
        dialog.connect('response', lambda _d, response: response == 'github' and self._open_on_github())
        dialog.present(self)

    def _show_thanks(self, number, url):
        page = Adw.StatusPage(icon_name='object-select-symbolic', title=_('Thanks for reporting!'),
                              description=_('Reported as #{number}. You can follow it on GitHub.')
                              .format(number=number))
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        if url:
            view = Gtk.Button(label=_('View on GitHub'))
            view.connect('clicked', lambda _b: self._open(url))
            buttons.append(view)
        done = Gtk.Button(label=_('Done'))
        done.add_css_class('suggested-action')
        done.connect('clicked', lambda _b: self.close())
        buttons.append(done)
        page.set_child(buttons)
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(Adw.HeaderBar())
        self.stack.add_named(view, 'thanks')
        self.stack.set_visible_child_name('thanks')

    def _open_on_github(self):
        title, description = self._texts()
        body = f'{description}\n\n---\n{self.details}'
        query = urlencode({'title': title, 'body': body}, quote_via=quote)
        self._open(f'https://github.com/{REPO}/issues/new?{query}')
        self.close()

    def _open(self, url):
        Gtk.UriLauncher.new(url).launch(self.get_root(), None, None)
