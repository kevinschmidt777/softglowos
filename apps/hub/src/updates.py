"""SoftglowOS updates: which version is installed, which one apt offers, what
the CHANGELOG says about them, and checking or installing them through
/usr/libexec/softglowos-update (pkexec, no password for administrators).

The version comes from VERSION, the packages carry it as "1.0.1~<build>".
A new build of the same version updates quietly in the background
(unattended-upgrades); only a new version number is announced."""

import os
import re
import subprocess

from gi.repository import Gio, GLib

from .version import version

PACKAGE = 'softglowos-hub'
HELPER = '/usr/libexec/softglowos-update'
CHANGELOG_URL = 'https://kevinschmidt777.github.io/softglowos/CHANGELOG.md'
LOCAL_CHANGELOG = '/usr/share/softglowos/CHANGELOG.md'
SECTION = re.compile(r'^## \[(\d+(?:\.\d+)*)\]')


def installed_version():
    return version()[0]


def available_version():
    """The SoftglowOS version apt would install, from the package lists the
    system keeps fresh (apt-daily); empty if unknown."""
    try:
        output = subprocess.run(['apt-cache', 'policy', PACKAGE], capture_output=True,
                                text=True, timeout=30, env={**os.environ, 'LC_ALL': 'C'}).stdout
    except (OSError, subprocess.SubprocessError):
        return ''
    match = re.search(r'^\s*Candidate:\s*(\S+)', output, re.MULTILINE)
    if not match or match.group(1) == '(none)':
        return ''
    return upstream(match.group(1))


def upstream(package_version):
    """"1:1.0.1~202611082044" -> "1.0.1"."""
    return package_version.split(':', 1)[-1].split('~', 1)[0].split('-', 1)[0]


def _key(number):
    return tuple(int(part) if part.isdigit() else 0 for part in number.split('.'))


def newer(a, b):
    """Whether version a is newer than b (both like "1.0.1")."""
    return bool(a) and (not b or _key(a) > _key(b))


def update_available():
    """The new version, or empty when SoftglowOS is up to date."""
    available = available_version()
    return available if newer(available, installed_version()) else ''


# CHANGELOG.md (Keep a Changelog)

def parse_changelog(text):
    """{version: [(heading, [entry, …]), …]} for every released version.
    Markdown is reduced to plain text for labels."""
    releases = {}
    groups = None
    entry = None
    for line in text.splitlines():
        match = SECTION.match(line)
        if match:
            groups = releases.setdefault(match.group(1), [])
            entry = None
            continue
        if line.startswith('## '):
            groups = entry = None  # [Unreleased]
            continue
        if groups is None:
            continue
        if line.startswith('### '):
            groups.append((line[4:].strip(), []))
            entry = None
        elif line.startswith('- ') and groups:
            entry = [line[2:].strip()]
            groups[-1][1].append(entry)
        elif line.startswith('  ') and entry is not None and line.strip():
            entry.append(line.strip())
        elif not line.strip():
            entry = None
    return {number: [(heading, [_plain(' '.join(parts)) for parts in entries])
                     for heading, entries in sections if entries]
            for number, sections in releases.items()}


def _plain(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)  # links
    return re.sub(r'\*\*|`', '', text)


def notes_between(changelog, old, new):
    """The changelog sections after version old up to and including new,
    newest first."""
    return [(number, changelog[number]) for number in sorted(changelog, key=_key, reverse=True)
            if newer(number, old) and not newer(number, new)]


def local_changelog():
    try:
        with open(LOCAL_CHANGELOG, encoding='utf-8') as file:
            return parse_changelog(file.read())
    except OSError:
        return {}


def fetch_changelog(callback):
    """Loads the CHANGELOG.md published with the apt repository (it knows the
    versions this system doesn't have yet); callback({…}) gets {} offline."""
    file = Gio.File.new_for_uri(CHANGELOG_URL)

    def loaded(_file, result):
        try:
            _ok, data, _etag = file.load_contents_finish(result)
            callback(parse_changelog(data.decode('utf-8', errors='replace')))
        except GLib.Error:
            callback({})
    file.load_contents_async(None, loaded)


# Checking and installing (as root, through pkexec)

def run_helper(command, callback, on_line=None):
    """Runs softglowos-update check|upgrade; callback(ok, output) when it's
    done, on_line(text) for every line of output while it runs."""
    try:
        process = Gio.Subprocess.new(
            ['pkexec', HELPER, command],
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
    except GLib.Error as error:
        callback(False, error.message)
        return
    stream = Gio.DataInputStream.new(process.get_stdout_pipe())
    lines = []

    def read_line(_stream, result):
        try:
            line, _length = stream.read_line_finish_utf8(result)
        except GLib.Error:
            line = None
        if line is not None:
            lines.append(line)
            if on_line and line.strip():
                on_line(line.strip())
            stream.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)
            return
        process.wait_async(None, finished)

    def finished(_process, result):
        try:
            process.wait_finish(result)
            ok = process.get_successful()
        except GLib.Error:
            ok = False
        callback(ok, '\n'.join(lines[-40:]))

    stream.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)
