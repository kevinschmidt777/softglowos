"""Crash reports, only with the user's consent (off by default; asked in the
setup assistant, changeable in the Hub's settings).

Our own apps report their Python exceptions here: they go into the queue
that softglowos-crash-reporter (a user service) sends to softglowos.com,
together with system details and the crashes of other programs."""

import json
import re
import sys
import time
import traceback
import uuid
from pathlib import Path

from gi.repository import GLib

CONSENT = Path(GLib.get_user_config_dir()) / 'softglowos' / 'crash-reports.json'
QUEUE = Path(GLib.get_user_state_dir()) / 'softglowos' / 'crash-reports'
PRIVACY_URL = {'de': 'https://softglowos.com/de/datenschutz', 'en': 'https://softglowos.com/en/privacy'}
HOME_PATHS = re.compile(r'/(?:var/)?home/[^/\s\'"()]+')


def enabled():
    try:
        return json.loads(CONSENT.read_text()).get('enabled') is True
    except (OSError, ValueError):
        return False


def set_enabled(on):
    CONSENT.parent.mkdir(parents=True, exist_ok=True)
    CONSENT.write_text(json.dumps({'enabled': bool(on)}))


def _scrub(text):
    return HOME_PATHS.sub('~', text).replace(str(Path.home()), '~')


def install(program):
    """Reports uncaught exceptions of this app (they still get printed)."""
    previous = sys.excepthook

    def hook(kind, value, tb):
        previous(kind, value, tb)
        if not enabled():
            return
        try:
            frames = [_scrub(f'File "{f.filename}", line {f.lineno}, in {f.name}')
                      for f in reversed(traceback.extract_tb(tb))]
            exception = _scrub(''.join(traceback.format_exception_only(kind, value)).strip())
            QUEUE.mkdir(parents=True, exist_ok=True)
            (QUEUE / f'{int(time.time())}-{uuid.uuid4().hex[:8]}.json').write_text(json.dumps({
                'kind': 'app', 'program': program, 'exception': exception[:300], 'frames': frames[:30],
            }))
        except OSError:
            pass  # never let reporting break the app

    sys.excepthook = hook
