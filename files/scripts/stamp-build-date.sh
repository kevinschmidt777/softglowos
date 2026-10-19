#!/usr/bin/env bash
# The version (VERSION in the repo) stays the same across the daily rebuilds,
# so the build date tells those images apart: the Hub shows it next to the
# version, bug and crash reports send it along.
set -euo pipefail

date -u +%Y-%m-%d > /usr/share/softglowos/build-date
cat /usr/share/softglowos/version /usr/share/softglowos/build-date
