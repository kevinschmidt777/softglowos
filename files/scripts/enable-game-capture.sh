#!/usr/bin/env bash
# Lets OBS's "Game Capture" source grab games straight from their Vulkan
# output (obs-vkcapture): Steam, Heroic and Lutris start every game with
# OBS_VKCAPTURE=1, so nobody has to add a launch option per game. Only these
# launchers, nothing system-wide. A game that shouldn't be captured gets the
# launch option OBS_VKCAPTURE=0.
set -euo pipefail

for app in steam com.heroicgameslauncher.hgl net.lutris.Lutris; do
  file="/usr/share/applications/$app.desktop"
  # Fail the build if a launcher renamed its desktop file
  [ -f "$file" ] || { echo "Missing $file" >&2; exit 1; }
  sed -i -E '/^Exec=env OBS_VKCAPTURE=1 /! s/^Exec=/Exec=env OBS_VKCAPTURE=1 /' "$file"
  grep '^Exec=' "$file"
done
