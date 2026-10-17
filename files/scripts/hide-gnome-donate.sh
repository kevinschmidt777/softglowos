#!/usr/bin/env bash
# Hides the "Support GNOME / Donate" banner on Settings > System > About.
# Settings has no switch for it, so we pull the page's UI file out of the
# current binary, drop the banner and let GLib load our copy instead
# (G_RESOURCE_OVERLAYS). Regenerated on every build, so it follows updates.
set -euo pipefail

RES=/org/gnome/control-center/system/about/cc-about-page.ui
OUT=/usr/share/softglowos/overlays/cc-about-page.ui

# gresource ships in glib2-devel; only pull it in for this step
if ! command -v gresource &>/dev/null; then
  dnf5 -y install /usr/bin/gresource
  trap 'dnf5 -y remove glib2-devel' EXIT
fi

mkdir -p "$(dirname "$OUT")"
gresource extract /usr/bin/gnome-control-center "$RES" | python3 -c '
import sys, xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.buffer.read())
parents = {c: p for p in root.iter() for c in p}
signals = [s for s in root.iter("signal") if s.get("handler") == "on_donate_button_clicked_cb"]
if not signals:
    sys.exit("donate banner not found in " + sys.argv[1])
# Walk up to the <child> that holds the banner group and remove it
node = signals[0]
while not (node.tag == "object" and node.get("class") == "AdwPreferencesGroup"):
    node = parents[node]
child = parents[node]
parents[child].remove(child)
sys.stdout.buffer.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))
' "$RES" > "$OUT"

# systemd user sessions read environment.d, so GNOME and its apps get it
echo "G_RESOURCE_OVERLAYS=$RES=$OUT" > /usr/lib/environment.d/60-softglowos-hide-donate.conf
