#!/usr/bin/env bash
# Adds to softglowos-base our shared files (files/) and
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

# Bluetooth keyboards and mice may wake the computer
take usr/lib/udev/rules.d/90-softglowos-bluetooth-wake.rules \
  usr/libexec/softglowos-bluetooth-wake

# The other internal disks mount at login without the password
take usr/libexec/softglowos-mount-disks \
  usr/lib/systemd/user/softglowos-mount-disks.service \
  usr/share/polkit-1/rules.d/50-softglowos-mount-disks.rules

# Look: wallpapers, branding, logo, GNOME defaults
take usr/share/backgrounds/softglowos \
  usr/share/gnome-background-properties/softglowos.xml \
  usr/share/softglowos/branding \
  usr/share/softglowos/fastfetch \
  usr/share/icons/hicolor/scalable/places/softglowos-logo.svg \
  etc/xdg/autostart/softglowos-close-overview.desktop \
  usr/libexec/softglowos-close-overview
mkdir -p "$DEST/usr/share/glib-2.0/schemas"
cp "$SRC/files/gschema-overrides/zz1-softglowos.gschema.override" "$DEST/usr/share/glib-2.0/schemas/"

# Fetch aliases with our logo
mkdir -p "$DEST/etc/profile.d"
cp "$SYSTEM/etc/profile.d/softglowos-fastfetch.sh" "$DEST/etc/profile.d/"

# Boot splash: Ubuntu's spinner theme with our wordmark (Bazzite uses the
# same theme). Login screen: the wordmark under the user list.
mkdir -p "$DEST/usr/share/plymouth/themes/softglowos"
rsvg-convert -h 64 "$SYSTEM/usr/share/softglowos/branding/wordmark-white.svg" \
  -o "$DEST/usr/share/plymouth/themes/softglowos/watermark.png"
rsvg-convert -h 48 "$SYSTEM/usr/share/softglowos/branding/wordmark-white.svg" \
  -o "$DEST/usr/share/softglowos/branding/gdm-logo.png"

# Settings > System > About: our wordmark in place of Ubuntu's (light and
# dark mode)
mkdir -p "$DEST/usr/share/pixmaps"
cp "$SYSTEM/usr/share/softglowos/branding/wordmark-dark.svg" "$DEST/usr/share/pixmaps/ubuntu-logo-text.svg"
cp "$SYSTEM/usr/share/softglowos/branding/wordmark-white.svg" "$DEST/usr/share/pixmaps/ubuntu-logo-text-dark.svg"

download() {  # url sha256 file
  curl -fsSL --retry 3 -o "$3" "$1" || { echo "Download failed: $1" >&2; return 1; }
  echo "$2  $3" | sha256sum -c --quiet -
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# GNOME Shell extensions, system-wide. Their schemas go to the global
# schema directory, so our gschema overrides apply to them.
extensions=$DEST/usr/share/gnome-shell/extensions
schemas=$DEST/usr/share/glib-2.0/schemas
mkdir -p "$extensions"
grep -vE '^\s*(#|$)' "$PACKAGE_DIR/extensions.list" | while read -r uuid _ tag sha256; do
  download "https://extensions.gnome.org/download-extension/$uuid.shell-extension.zip?version_tag=$tag" \
    "$sha256" "$tmp/$uuid.zip"
  unzip -q "$tmp/$uuid.zip" -d "$extensions/$uuid"
  # Our changes to an extension, made for the pinned version
  if [ -f "$PACKAGE_DIR/patches/$uuid.patch" ]; then
    patch -p1 --no-backup-if-mismatch -s -d "$extensions/$uuid" < "$PACKAGE_DIR/patches/$uuid.patch"
  fi
  # An extension prefers a schemas/ folder of its own, which would ignore our
  # overrides, so its schemas only live in the global directory
  if [ -d "$extensions/$uuid/schemas" ]; then
    cp "$extensions/$uuid/schemas/"*.gschema.xml "$schemas/"
    rm -rf "$extensions/$uuid/schemas"
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

# netplan only reads its files when nobody else can
chmod 600 "$DEST/etc/netplan/01-network-manager-all.yaml"
