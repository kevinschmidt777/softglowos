#!/usr/bin/env bash
# Hides Bazzite's own entries from the app grid: its documentation and forum
# links, its welcome portal, its updater and Steam's Big Picture Mode (we are
# a desktop OS). The programs stay installed; Bazzite scripts may call them.
# Fails the build if Bazzite renames one, so we notice.
set -euo pipefail

for app in \
  bazzite-documentation \
  discourse \
  io.github.ublue_os.yafti_gtk \
  io.github.rfrench3.bazzite-updater \
  bazzite-steam-bpm; do
  desktop-file-edit --set-key=NoDisplay --set-value=true "/usr/share/applications/$app.desktop"
done
