#!/usr/bin/env bash
# Shared with the Fedora image: GTK 4 apps get the GL renderer while nouveau
# runs, which on Ubuntu is until the NVIDIA driver is installed
set -euo pipefail

generator=usr/lib/systemd/user-environment-generators/60-softglowos-nouveau
install -D -m 755 "$SRC/files/system/$generator" "$DEST/$generator"
