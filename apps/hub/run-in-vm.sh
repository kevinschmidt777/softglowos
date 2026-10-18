#!/usr/bin/env bash
# Copy the Hub into the "SoftglowOS Dev" VM, build and install it there
# (into ~/.local) and start it on the VM's desktop.
# HUB_LANGUAGE picks the UI language (default: de).
set -euo pipefail

VM="${VM:-tester@192.168.64.3}"
SSH="ssh -i $HOME/.ssh/softglowos-dev -o UserKnownHostsFile=$HOME/.ssh/known_hosts_softglowos_dev"
HERE="$(cd "$(dirname "$0")" && pwd)"

rsync -a --delete --exclude build -e "$SSH" "$HERE/" "$VM:hub/"

$SSH "$VM" "HUB_LANGUAGE=${HUB_LANGUAGE:-de} bash -s" <<'EOF'
set -e
cd hub
[ -d build ] || meson setup build --prefix="$HOME/.local"
meson install -C build --quiet
systemctl --user stop softglowos-hub 2>/dev/null || true
systemctl --user reset-failed softglowos-hub 2>/dev/null || true
systemd-run --user --unit=softglowos-hub --setenv=LANGUAGE="$HUB_LANGUAGE" \
  "$HOME/.local/bin/softglowos-hub"
EOF
