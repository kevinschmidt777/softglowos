#!/usr/bin/env bash
# Downloads the newest official .deb of apps that Ubuntu doesn't have into
# ubuntu/out/, so they go into our repository and the ISO:
# - Heroic Games Launcher (GPL-3.0) and GoXLR Utility (MIT), checked against
#   the SHA-256 that GitHub lists for each release file
# - Valve's Steam launcher (steam-launcher, like Bazzite ships it), checked
#   against Valve's apt repository; once installed it adds that repository
#   and updates from there
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
