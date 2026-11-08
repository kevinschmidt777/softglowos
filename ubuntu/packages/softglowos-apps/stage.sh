#!/usr/bin/env bash
# StreamController and GoXLR Utility as on the Fedora image: the Stream Deck
# udev rule, the user services, our mixer plugin and StreamController's OBS
# plugin (fetched by the Fedora image's own script, same pin and checksum)
set -euo pipefail

SYSTEM=$SRC/files/system
take() {  # path [mode]
  install -D -m "${2:-644}" "$SYSTEM/$1" "$DEST/$1"
}

take usr/lib/udev/rules.d/60-softglowos-streamdeck.rules
take usr/lib/systemd/user/softglowos-streamcontroller.service
take usr/lib/systemd/user/goxlr-daemon.service
take usr/libexec/softglowos-streamcontroller 755

plugins=usr/share/softglowos/streamcontroller
mkdir -p "$DEST/$plugins"
cp -r "$SYSTEM/$plugins/com_softglowos_Mixer" "$DEST/$plugins/"
bash "$SRC/files/scripts/install-streamcontroller-plugins.sh" >/dev/null
cp -r "/$plugins/com_core447_OBSPlugin" "$DEST/$plugins/"
chmod -R u=rwX,go=rX "$DEST/$plugins"
