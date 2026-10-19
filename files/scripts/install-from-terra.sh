#!/usr/bin/env bash
# Installs Discord and the Heroic Games Launcher natively from the Terra
# repository that Bazzite already ships. The repository may be disabled by
# default, so enable it for this transaction only. Discord downloads the
# actual app on first start (Discord's official way).
set -euo pipefail

dnf5 -y --enable-repo=terra install discord heroic-games-launcher
