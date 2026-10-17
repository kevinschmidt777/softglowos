#!/usr/bin/env sh
# SoftglowOS replacement for Bazzite's MOTD environment.
# Runs on every new shell, so keep it small: pick the colors and the template by language.

# Bazzite ships glow themes but never selects one; glow's default uses violet and red
export GLOW_STYLE="${GLOW_STYLE:-/usr/share/ublue-os/motd/themes/teal.json}"

case "${LC_MESSAGES:-${LANG:-C}}" in
  de*) export MOTD_TEMPLATE_FILE="${MOTD_TEMPLATE_FILE:-/usr/share/ublue-os/motd/template.de.md}" ;;
esac
