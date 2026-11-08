#!/usr/bin/env bash
# Downloads the newest official .deb of apps that Ubuntu doesn't have into
# ubuntu/out/, so they go into our repository and the ISO:
# - Heroic Games Launcher (GPL-3.0) and GoXLR Utility (MIT), checked against
#   the SHA-256 that GitHub lists for each release file
# - Valve's Steam launcher (steam-launcher, like Bazzite ships it), checked
#   against Valve's apt repository; once installed it adds that repository
#   and updates from there
# - OpenRGB (GPL-2.0) with its hidapi build, pinned: Ubuntu only has a 0.9
#   snapshot from 2025, the Bazzite image a 1.0; Codeberg lists no
#   checksums, so the version and SHA-256 are fixed here
set -euo pipefail

OUT=$(cd "$(dirname "$0")" && pwd)/out
mkdir -p "$OUT"

mirror() {  # owner/repo name-pattern
  local asset url digest file
  asset=$(curl -fsSL --retry 3 ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
    "https://api.github.com/repos/$1/releases/latest" |
    jq -c --arg re "$2" '[.assets[] | select(.name | test($re))][0]')
  url=$(jq -r .browser_download_url <<<"$asset")
  digest=$(jq -r '.digest // empty' <<<"$asset")
  [ -n "$digest" ] || { echo "No checksum for $url" >&2; return 1; }
  file="$OUT/$(basename "$url")"
  echo "==> $url"
  curl -fsSL --retry 10 --retry-all-errors --retry-delay 15 -o "$file" "$url"
  echo "${digest#sha256:}  $file" | sha256sum -c --quiet -
}

mirror Heroic-Games-Launcher/HeroicGamesLauncher '^Heroic-.*-linux-amd64\.deb$'
mirror GoXLR-on-Linux/goxlr-utility '^goxlr-utility_.*_amd64\.deb$'

# Valve's Steam: the newest steam-launcher in Valve's repository index
steam() {
  local repo=https://repo.steampowered.com/steam url sha256 file
  read -r _ url sha256 < <(curl -fsSL --retry 10 --retry-all-errors --retry-delay 15 \
    "$repo/dists/stable/steam/binary-amd64/Packages" |
    awk -v RS= -F'\n' '/(^|\n)Package: steam-launcher(\n|$)/ {
      for (i = 1; i <= NF; i++) { split($i, kv, ": "); f[kv[1]] = kv[2] }
      print f["Version"], f["Filename"], f["SHA256"] }' | sort -V | tail -n 1)
  [ -n "${sha256:-}" ] || { echo "steam-launcher not found in Valve's index" >&2; return 1; }
  file="$OUT/$(basename "$url")"
  echo "==> $repo/$url"
  curl -fsSL --retry 10 --retry-all-errors --retry-delay 15 -o "$file" "$repo/$url"
  echo "$sha256  $file" | sha256sum -c --quiet -
}
steam

# OpenRGB from Codeberg, the Debian 13 (trixie) builds
pinned() {  # url sha256
  local file
  file="$OUT/$(basename "$1")"
  echo "==> $1"
  curl -fsSL --retry 10 --retry-all-errors --retry-delay 15 -o "$file" "$1"
  echo "$2  $file" | sha256sum -c --quiet -
}
CODEBERG=https://codeberg.org/OpenRGB
pinned "$CODEBERG/OpenRGB/releases/download/release_1.1/openrgb_1.1_amd64_trixie_8e16de2.deb" \
  45d1ecf6a5d7b8e309ec6edd45a5759eac4eff14101ed210a87b88d121747d25
pinned "$CODEBERG/hidapi-hotplug/releases/download/hidapi-hotplug-0.15.0/libhidapi-hotplug-hidraw0_0.15.0-1_trixie_amd64.deb" \
  4c12ad429aad50b6e38ff7a04be37268a2401b76884d4067f70ed9df37ebbd2d
pinned "$CODEBERG/hidapi-hotplug/releases/download/hidapi-hotplug-0.15.0/libhidapi-hotplug-libusb0_0.15.0-1_trixie_amd64.deb" \
  ff4c563d396a80acd876454bf831af3e6578e4bd1d0b5b47990f75e6577450a6
