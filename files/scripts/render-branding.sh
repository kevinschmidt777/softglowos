#!/usr/bin/env bash
# Renders the branding from SVG sources into the PNGs that Plymouth (boot
# splash) and GDM (login screen) expect, and replaces the leftover logos.
set -euo pipefail

SRC=/usr/share/softglowos/branding

# Only pull in rsvg-convert temporarily if the base image doesn't ship it
if ! rpm -q librsvg2-tools &>/dev/null; then
  dnf5 -y install librsvg2-tools
  trap 'dnf5 -y remove librsvg2-tools' EXIT
fi

# Boot splash watermark of the spinner theme Bazzite uses
rsvg-convert -h 64 "$SRC/wordmark-white.svg" \
  -o /usr/share/plymouth/themes/spinner/watermark.png

# Login screen logo (GDM reads this path via Fedora's dconf defaults)
rsvg-convert -h 48 "$SRC/wordmark-white.svg" \
  -o /usr/share/pixmaps/fedora-gdm-logo.png

# Settings > System > About: Fedora patches it to show these two files
# (light and dark mode) instead of the os-release LOGO icon
rsvg-convert -h 80 "$SRC/wordmark-dark.svg" -o /usr/share/pixmaps/fedora_logo_med.png
rsvg-convert -h 80 "$SRC/wordmark-white.svg" -o /usr/share/pixmaps/fedora_whitelogo_med.png

# Every other distro logo left from Bazzite and Fedora: icons that apps show
# as "the distro logo" (start-here, distributor-logo, ...) and the pixmaps
# Plymouth and other tools fall back to. Same file, same size, our logo.
LOGO=/usr/share/icons/hicolor/scalable/places/softglowos-logo.svg
png_height() {
  python3 -c 'import struct, sys; print(struct.unpack(">I", open(sys.argv[1], "rb").read(24)[20:24])[0])' "$1"
}
replace() {
  local src=$1 target
  for target in "${@:2}"; do
    [ -e "$target" ] || continue  # not every base image has every file
    case "$target" in
      *.svg) cp "$src" "$target" ;;
      *.png) rsvg-convert -h "$(png_height "$target")" "$src" -o "$target" ;;
    esac
  done
}
replace "$LOGO" \
  /usr/share/icons/hicolor/*/places/start-here.png \
  /usr/share/icons/hicolor/scalable/{apps,places}/start-here.svg \
  /usr/share/icons/hicolor/scalable/places/{distributor-logo,distributor-logo-white,distributor-logo-steamdeck}.svg \
  /usr/share/icons/hicolor/scalable/places/{bazzite-logo,bazzite-logo-white,bazzite-logo-le}.svg \
  /usr/share/icons/hicolor/*/apps/fedora-logo-icon.png \
  /usr/share/icons/hicolor/*/bazzite-logo-icon.png \
  /usr/share/pixmaps/system-logo-white.png \
  /usr/share/pixmaps/fedora-logo-sprite.{png,svg}
replace "$SRC/wordmark-dark.svg" /usr/share/pixmaps/fedora-logo.png /usr/share/pixmaps/fedora-logo-small.png
replace "$SRC/wordmark-white.svg" /usr/share/pixmaps/fedora_whitelogo.svg

# "Bazzite release 44 (Silverblue)" -> "SoftglowOS release 44 (Silverblue)"
# A link to /usr/lib/fedora-release, which /etc/redhat-release shares
sed -i --follow-symlinks 's/^Bazzite release/SoftglowOS release/' /etc/system-release
grep -q '^SoftglowOS release' /etc/system-release

# Our OS logo (os-release LOGO) lives in hicolor; ostree resets file times, so
# GTK would trust the stale icon cache and never find it without a refresh
gtk-update-icon-cache -f /usr/share/icons/hicolor
