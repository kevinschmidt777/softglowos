#!/usr/bin/env bash
# Builds and installs the Hub (apps/hub, copied to /tmp/softglowos-hub by the
# recipe). The build tools are only installed for this step.
set -euo pipefail

SRC=/tmp/softglowos-hub
BUILD_DEPS=(meson blueprint-compiler)

missing=()
for pkg in "${BUILD_DEPS[@]}"; do
  rpm -q "$pkg" &>/dev/null || missing+=("$pkg")
done
if [ ${#missing[@]} -gt 0 ]; then
  dnf5 -y install "${missing[@]}"
  trap 'dnf5 -y remove "${missing[@]}"' EXIT
fi

meson setup /tmp/hub-build "$SRC" --prefix=/usr
meson install -C /tmp/hub-build
rm -rf /tmp/hub-build "$SRC"

# The Hub is the only GoXLR interface: the GoXLR Utility daemon keeps running
# in the background as the driver, but its own app entry goes away, so there
# are no two places with the same settings.
desktop-file-edit --set-key=NoDisplay --set-value=true /usr/share/applications/goxlr-utility.desktop
