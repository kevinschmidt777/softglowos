#!/usr/bin/env bash
# Installs Discord natively from the Terra repository that Bazzite already
# ships. The repository may be disabled by default, so enable it for this
# transaction only.
set -euo pipefail

dnf5 -y --enable-repo=terra install discord
