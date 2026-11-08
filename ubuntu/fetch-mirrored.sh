#!/usr/bin/env bash
# Downloads the newest official .deb of the open-source apps without an apt
# repository of their own into ubuntu/out/, so they go into ours: Heroic
# Games Launcher (GPL-3.0) and GoXLR Utility (MIT). Checked against the
# SHA-256 that GitHub lists for each release file.
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
