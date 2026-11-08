#!/usr/bin/env bash
# Boots the ISO in QEMU with UEFI and Secure Boot on (OVMF with Microsoft's
# keys, like a normal PC) and takes screenshots along the way, so a broken
# boot shows before anyone writes the ISO to a USB stick. Needs KVM.
#   ubuntu/iso/boot-test.sh <iso> <screenshot folder>
set -euo pipefail

iso=$1
shots=$2
mkdir -p "$shots"
tmp=$(mktemp -d)
cp /usr/share/OVMF/OVMF_VARS_4M.ms.fd "$tmp/vars.fd"

qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m 6G \
  -machine q35,smm=on -global driver=cfi.pflash01,property=secure,value=on \
  -drive if=pflash,format=raw,unit=0,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd \
  -drive if=pflash,format=raw,unit=1,file="$tmp/vars.fd" \
  -cdrom "$iso" -vga virtio -display none \
  -qmp unix:"$tmp/qmp.sock",server,nowait &
qemu=$!
trap 'kill $qemu 2>/dev/null || :; rm -rf "$tmp"' EXIT

shot() {  # name
  printf '{"execute":"qmp_capabilities"}\n{"execute":"screendump","arguments":{"filename":"%s"}}\n' \
    "$tmp/$1.ppm" | socat - UNIX-CONNECT:"$tmp/qmp.sock" >/dev/null
  sleep 2
  convert "$tmp/$1.ppm" "$shots/$1.png"
}

# The boot menu, the boot splash, then the live session with the installer
for at in 5 30 90 180 300; do
  sleep $((at - ${last:-0}))
  last=$at
  kill -0 $qemu 2>/dev/null || { echo "QEMU stopped" >&2; exit 1; }
  shot "$(printf '%03ds' "$at")"
done
ls "$shots"
