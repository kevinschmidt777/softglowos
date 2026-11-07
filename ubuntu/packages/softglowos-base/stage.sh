#!/usr/bin/env bash
# Adds to softglowos-base what it shares with the Bazzite image (files/) and
# what it downloads: GNOME Shell extensions and the Geist fonts.
set -euo pipefail

SYSTEM=$SRC/files/system
GEIST_VERSION=1.9.2
GEIST_SHA256=15f066d58dcb99fb10014a49913009fdaf41e464cfb8851a44b44e593c95d3d8

take() {
  local path
  for path in "$@"; do
    mkdir -p "$DEST/$(dirname "$path")"
    cp -a "$SYSTEM/$path" "$DEST/$path"
  done
}

# Audio: PipeWire clock, the mixer's sinks and WirePlumber's routing script
take usr/share/pipewire/pipewire.conf.d \
  usr/share/wireplumber \
  usr/lib/systemd/user/pipewire.service.d

# Look: wallpapers, branding, logo, GNOME defaults shared with Fedora
take usr/share/backgrounds/softglowos \
  usr/share/gnome-background-properties/softglowos.xml \
  usr/share/softglowos/branding \
  usr/share/softglowos/fastfetch \
  usr/share/icons/hicolor/scalable/places/softglowos-logo.svg \
  etc/xdg/autostart/softglowos-close-overview.desktop \
  usr/libexec/softglowos-close-overview
mkdir -p "$DEST/usr/share/glib-2.0/schemas"
cp "$SRC/files/gschema-overrides/zz1-softglowos.gschema.override" "$DEST/usr/share/glib-2.0/schemas/"

# Fetch aliases with our logo (Fedora replaces Bazzite's file of this name)
mkdir -p "$DEST/etc/profile.d"
cp "$SYSTEM/etc/profile.d/bazzite-neofetch.sh" "$DEST/etc/profile.d/softglowos-fastfetch.sh"

# Boot splash: Ubuntu's spinner theme with our wordmark (Bazzite uses the
# same theme). Login screen: the wordmark under the user list.
mkdir -p "$DEST/usr/share/plymouth/themes/softglowos"
rsvg-convert -h 64 "$SYSTEM/usr/share/softglowos/branding/wordmark-white.svg" \
  -o "$DEST/usr/share/plymouth/themes/softglowos/watermark.png"
rsvg-convert -h 48 "$SYSTEM/usr/share/softglowos/branding/wordmark-white.svg" \
  -o "$DEST/usr/share/softglowos/branding/gdm-logo.png"

download() {  # url sha256 file
  curl -fsSL --retry 3 -o "$3" "$1"
  echo "$2  $3" | sha256sum -c --quiet -
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# GNOME Shell extensions, system-wide. Their schemas also go to the global
# schema directory, so our gschema overrides apply to them.
extensions=$DEST/usr/share/gnome-shell/extensions
schemas=$DEST/usr/share/glib-2.0/schemas
mkdir -p "$extensions"
grep -vE '^\s*(#|$)' "$PACKAGE_DIR/extensions.list" | while read -r uuid _ tag sha256; do
  download "https://extensions.gnome.org/download-extension/$uuid.shell-extension.zip?version_tag=$tag" \
    "$sha256" "$tmp/$uuid.zip"
  unzip -q "$tmp/$uuid.zip" -d "$extensions/$uuid"
  rm -f "$extensions/$uuid/schemas/gschemas.compiled"
  if [ -d "$extensions/$uuid/schemas" ]; then
    cp "$extensions/$uuid/schemas/"*.gschema.xml "$schemas/"
    # The extensions read their compiled schemas next to them
    glib-compile-schemas "$extensions/$uuid/schemas"
  fi
  chmod -R u=rwX,go=rX "$extensions/$uuid"
done

# Geist and Geist Mono (OFL-1.1), variable fonts
download "https://github.com/vercel/geist-font/releases/download/v$GEIST_VERSION/geist-font-v$GEIST_VERSION.zip" \
  "$GEIST_SHA256" "$tmp/geist.zip"
unzip -q "$tmp/geist.zip" -d "$tmp/geist"
fonts=$DEST/usr/share/fonts/truetype/geist
mkdir -p "$fonts"
cp "$tmp"/geist/geist-font/{Geist,GeistMono}/variable/*.ttf "$fonts/"
cp "$tmp/geist/geist-font/OFL.txt" "$fonts/" 2>/dev/null || :
chmod 644 "$fonts"/*
