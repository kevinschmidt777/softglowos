#!/usr/bin/env sh
# Streamer OS replacement for Bazzite's MOTD environment.
# Runs on every new shell, so keep it small: only pick the template by language.

case "${LC_MESSAGES:-${LANG:-C}}" in
  de*) export MOTD_TEMPLATE_FILE="${MOTD_TEMPLATE_FILE:-/usr/share/ublue-os/motd/template.de.md}" ;;
esac
