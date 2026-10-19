#!/usr/bin/env bash
# Keeps the microphone indicator in the top bar meaningful. Our mixer records
# its own channels and the microphone all the time (that's how the mic filters
# and the stream mix work), and GNOME Shell would count every one of those
# streams as "an app is recording". We teach the indicator to skip streams
# named softglowos.*, the same way it already skips Settings and pavucontrol.
# Real recordings (OBS, Discord, ...) still show it.
# The file is pulled out of the current GNOME Shell and patched on every
# build (G_RESOURCE_OVERLAYS), so it follows updates; the build fails if the
# code it patches ever changes.
set -euo pipefail

RES=/org/gnome/shell/ui/status/volume.js
OUT=/usr/share/softglowos/overlays/volume.js
LIB=$(ls /usr/lib64/gnome-shell/libshell-*.so | head -n1)

# gresource ships in glib2-devel; only pull it in for this step
if ! command -v gresource &>/dev/null; then
  dnf5 -y install /usr/bin/gresource
  trap 'dnf5 -y remove glib2-devel' EXIT
fi

mkdir -p "$(dirname "$OUT")"
gresource extract "$LIB" "$RES" | python3 -c '
import sys
code = sys.stdin.read()
old = ".get_source_outputs().some("
# Gvc keeps the media.name of a source output as its description, its name is null
new = (".get_source_outputs()"
       ".filter(o => ![o.get_name(), o.get_description()]"
       ".some(n => (n ?? \"\").startsWith(\"softglowos.\"))).some(")
if code.count(old) != 1:
    for number, line in enumerate(code.splitlines(), 1):
        if "source_output" in line or "skippedApps" in line:
            print(f"{number}: {line}", file=sys.stderr)
    sys.exit("mic indicator code not found in " + sys.argv[1])
sys.stdout.write(code.replace(old, new))
' "$RES" > "$OUT"

# Appends to the overlay list of hide-gnome-donate.sh (environment.d files are
# read in order and may expand variables set by earlier files)
echo "G_RESOURCE_OVERLAYS=\${G_RESOURCE_OVERLAYS:+\${G_RESOURCE_OVERLAYS}:}$RES=$OUT" \
  > /usr/lib/environment.d/61-softglowos-mic-indicator.conf
