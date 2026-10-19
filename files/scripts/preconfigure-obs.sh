#!/usr/bin/env bash
# OBS's app entry starts softglowos-obs, which prepares encoder and mixer
# audio on the very first start and then runs OBS (see that script).
set -euo pipefail

file=/usr/share/applications/com.obsproject.Studio.desktop
# Fail the build if OBS renamed its desktop file or its Exec line changed
grep -qx 'Exec=obs' "$file"
sed -i 's|^Exec=obs$|Exec=softglowos-obs|' "$file"
grep '^Exec=' "$file"
