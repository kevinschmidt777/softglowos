#!/usr/bin/env bash
# Removes ujust recipes that break or make no sense on SoftglowOS. ujust stays
# for power users otherwise. Fails the build if Bazzite renames one, so we notice.
set -euo pipefail

JUST_DIR=/usr/share/ublue-os/just

python3 - "$JUST_DIR" <<'EOF'
import re
import sys
from pathlib import Path

REMOVE = {
    # Overwrite our GNOME defaults and app folders with Bazzite's
    "restore-gnome-de-settings", "restore-gnome-folders",
    # Swaps the shell setup, including our terminal greeting
    "bazzite-cli",
    # Virtual sinks that clash with our own audio mixer
    "setup-virtual-channels",
    # OpenRGB ships natively in the image
    "openrgb",
    # Steam Gaming Mode, Steam Deck and Decky; we are a desktop OS
    "set-default-game-mode", "set-default-desktop",
    "setup-decky", "get-decky-bazzite-buddy", "get-decky-lossless-scaling", "get-framegen",
    "add-updater-to-steam", "add-protonplus-to-steam",
    # Show Bazzite's release notes, not ours
    "changelogs", "changelogs-testing",
}

# May only exist in the NVIDIA image, so not required. It rebases between the NVIDIA
# driver and NVK behind the Hub's back; the Hub picks the image itself.
OPTIONAL = {"toggle-nvk"}
REMOVE |= OPTIONAL

header = re.compile(r"^([a-z0-9-]+)(\s[^:]*)?:(?!=)")
alias = re.compile(r"^alias\s+\S+\s*:=\s*([a-z0-9-]+)\s*$")
found = set()

for path in sorted(Path(sys.argv[1]).glob("*.just")):
    lines = path.read_text().splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        match = header.match(lines[i])
        if match and match.group(1) in REMOVE:
            found.add(match.group(1))
            # Drop the doc comment and attributes right above the recipe
            while out and out[-1].startswith(("#", "[")):
                out.pop()
            # Drop the recipe body: everything indented or blank
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                i += 1
            continue
        match = alias.match(lines[i])
        if match and match.group(1) in REMOVE:
            i += 1
            continue
        out.append(lines[i])
        i += 1
    path.write_text("".join(out))

missing = REMOVE - OPTIONAL - found
if missing:
    sys.exit(f"ujust recipes not found: {', '.join(sorted(missing))}")
EOF

# The ujust overview links to Bluefin's documentation
grep -q 'docs.projectbluefin.io' /usr/share/ublue-os/justfile
sed -i '/docs.projectbluefin.io/d' /usr/share/ublue-os/justfile

# Make sure the justfile still parses
just --justfile /usr/share/ublue-os/justfile --summary >/dev/null
