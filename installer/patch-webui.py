#!/usr/bin/python3
"""Adjusts Anaconda's web UI for the live system.

The finish button reads "Restart system" (softglowos-installer restarts once
the installer closes after installing), and the German translation addresses
people with "du" (webui-de-du.json). A text missing from the catalog is
added, so a newer Anaconda with changed texts still builds.
"""
import gzip
import json
import re
import sys
from pathlib import Path

WEBUI = Path("/usr/share/cockpit/anaconda-webui")


def rewrite(path, change):
    text = gzip.decompress(path.read_bytes()).decode()
    path.write_bytes(gzip.compress(change(text).encode()))


def finish_button(js):
    if '"Exit to live desktop"' not in js:
        sys.exit("patch-webui: finish button text not found in index.js")
    return js.replace('"Exit to live desktop"', '"Restart system"')


def german(catalog):
    for msgid, text in json.loads(Path(sys.argv[1]).read_text()).items():
        key = json.dumps(msgid, ensure_ascii=False)
        value = json.dumps(text, ensure_ascii=False)
        entry = re.compile(r'(\n ' + re.escape(key) + r': \[\s*null,\s*)"(?:[^"\\]|\\.)*"')
        catalog, found = entry.subn(lambda m: m.group(1) + value, catalog)
        if not found:
            catalog = catalog.replace("cockpit.locale({\n", f"cockpit.locale({{\n {key}: [null, {value}],\n", 1)
    return catalog


rewrite(WEBUI / "index.js.gz", finish_button)
rewrite(WEBUI / "po.de.js.gz", german)
