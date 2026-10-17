#!/usr/bin/env bash
# Removes autostart entries Bazzite ships that do not fit SoftglowOS:
# its welcome portal and announcements (Bazzite branding; our own setup
# assistant replaces them) and Steam starting on login (Steam stays installed).
set -euo pipefail

rm -f \
  /etc/skel/.config/autostart/bazzite-portal.desktop \
  /etc/skel/.config/autostart/steam.desktop \
  /etc/xdg/autostart/bazzite-announcement.desktop
