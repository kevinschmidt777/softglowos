#!/usr/bin/env bash
# Copy our PipeWire and WirePlumber files into the "SoftglowOS Dev" VM at the
# same paths as in the image, and restart the audio services if anything changed.
set -euo pipefail

VM="${VM:-tester@192.168.64.3}"
SSH="ssh -i $HOME/.ssh/softglowos-dev -o UserKnownHostsFile=$HOME/.ssh/known_hosts_softglowos_dev"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

$SSH "$VM" mkdir -p softglowos-audio
rsync -a --delete -e "$SSH" "$ROOT/files/system/usr/share/pipewire/" "$VM:softglowos-audio/pipewire/"
rsync -a --delete -e "$SSH" "$ROOT/files/system/usr/share/wireplumber/" "$VM:softglowos-audio/wireplumber/"

$SSH "$VM" 'bash -s' <<'EOF'
set -e
changed=$(echo streamer | sudo -S -p "" rsync -a -i \
  ~/softglowos-audio/pipewire/ /usr/share/pipewire/ ; \
  echo streamer | sudo -S -p "" rsync -a -i \
  ~/softglowos-audio/wireplumber/ /usr/share/wireplumber/)
if [ -n "$changed" ]; then
  echo "$changed"
  systemctl --user restart pipewire pipewire-pulse wireplumber
  echo "audio services restarted"
fi
EOF
