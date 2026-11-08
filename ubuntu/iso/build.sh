#!/usr/bin/env bash
# Builds the SoftglowOS live ISO from Ubuntu 26.04 and our packages. Runs as
# root in a privileged ubuntu:26.04 container (see the ISO job in
# .github/workflows/ubuntu-packages.yml):
#   /src   the repository
#   /debs  our .deb packages plus Heroic and GoXLR Utility
#   /out   the ISO
#
# The ISO boots Ubuntu's signed shim and GRUB (Secure Boot) and the casper
# live system, a GNOME session that opens the installer (softglowos-installer,
# Calamares). Calamares copies the live system's squashfs, so the live system
# is the installed system minus softglowos-installer and casper. UEFI only.
set -euo pipefail

SUITE=resolute
MIRROR=http://archive.ubuntu.com/ubuntu
VERSION=$(cat /src/VERSION)
WORK=${WORK:-/work}
ROOT=$WORK/rootfs
ISO=$WORK/iso
export DEBIAN_FRONTEND=noninteractive

# Everything Calamares needs from Ubuntu besides our packages and their
# dependencies: the live boot, the GNOME apps Bazzite ships (as Ubuntu's
# packages), and what makes a desktop work (network, Bluetooth, printing,
# portals, firmware updates, power profiles, German and English).
PACKAGES=(
  linux-generic casper efibootmgr os-prober locales sudo
  language-pack-de language-pack-en language-pack-gnome-de language-pack-gnome-en
  network-manager wpasupplicant wireless-regdb bluez cups firmware-sof-signed
  pipewire-pulse pipewire-alsa libspa-0.2-bluetooth xwayland
  xdg-desktop-portal-gnome xdg-user-dirs-gtk gnome-keyring gvfs-backends
  gnome-control-center power-profiles-daemon fwupd unattended-upgrades
  nautilus ptyxis file-roller gnome-text-editor loupe papers showtime
  gnome-calculator gnome-calendar gnome-characters gnome-contacts gnome-clocks
  gnome-weather gnome-logs gnome-font-viewer gnome-firmware baobab
  gnome-system-monitor gnome-disk-utility gnome-shell-extension-manager flatseal
  distrobox podman fonts-noto-core fonts-noto-color-emoji curl unzip nano
)
# 32-bit parts for games through Steam (Ubuntu has no 32-bit MangoHud or vkBasalt)
PACKAGES_I386=(libgamemodeauto0:i386 mesa-vulkan-drivers:i386 libgl1-mesa-dri:i386)
# The Bazzite apps Ubuntu doesn't package, from Flathub
FLATPAKS=(
  com.core447.StreamController io.missioncenter.MissionCenter
  io.github.flattool.Warehouse com.vysp3r.ProtonPlus page.tesk.Refine
  com.ranfdev.DistroShelf
)

apt-get update -qq
apt-get install -y -qq debootstrap squashfs-tools xorriso mtools dosfstools apt-utils >/dev/null

in_root() {
  chroot "$ROOT" /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin HOME=/root \
    DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 "$@"
}

unmount_root() {
  for dir in run dev/pts dev sys proc; do
    umount -l "$ROOT/$dir" 2>/dev/null || :
  done
}
trap unmount_root EXIT

### The system ###

rm -rf "$ROOT" "$ISO" "$WORK/efi.img"
mkdir -p "$ROOT" "$ISO"
debootstrap --arch=amd64 --variant=minbase --components=main,restricted,universe,multiverse \
  "$SUITE" "$ROOT" "$MIRROR" >/dev/null
mount -t proc proc "$ROOT/proc"
mount -t sysfs sys "$ROOT/sys"
mount --bind /dev "$ROOT/dev"
mount --bind /dev/pts "$ROOT/dev/pts"
mount -t tmpfs tmpfs "$ROOT/run"
# DNS for the chroot: Ubuntu's resolv.conf points into /run
mkdir -p "$ROOT/run/systemd/resolve"
cp -L /etc/resolv.conf "$ROOT/run/systemd/resolve/stub-resolv.conf"

# No services start while building
printf '#!/bin/sh\nexit 101\n' > "$ROOT/usr/sbin/policy-rc.d"
chmod 755 "$ROOT/usr/sbin/policy-rc.d"

rm -f "$ROOT/etc/apt/sources.list"
cat > "$ROOT/etc/apt/sources.list.d/ubuntu.sources" <<EOF
Types: deb
URIs: $MIRROR
Suites: $SUITE $SUITE-updates $SUITE-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://security.ubuntu.com/ubuntu
Suites: $SUITE-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
# Snap stays out (docs/ubuntu-port.md)
cat > "$ROOT/etc/apt/preferences.d/no-snap" <<'EOF'
Package: snapd
Pin: release a=*
Pin-Priority: -10
EOF
in_root dpkg --add-architecture i386
in_root apt-get update -qq
in_root apt-get install -y -qq ca-certificates >/dev/null

# OBS's PPA, as softglowos-obs sets it up, so its OBS can be installed
# (HTTPS, so after ca-certificates)
cp /src/ubuntu/packages/softglowos-obs/root/etc/apt/sources.list.d/obs-studio.sources \
  "$ROOT/etc/apt/sources.list.d/"
cp /src/ubuntu/packages/softglowos-obs/root/usr/share/keyrings/obs-studio-ppa.asc \
  "$ROOT/usr/share/keyrings/"
in_root apt-get update -qq

mkdir -p "$ROOT/tmp/debs"
cp /debs/*.deb "$ROOT/tmp/debs/"
debs=()
for deb in "$ROOT"/tmp/debs/*.deb; do
  debs+=("/tmp/debs/${deb##*/}")
done
# Our packages with everything they recommend, like Ubuntu installs
in_root apt-get install -y -q "${PACKAGES[@]}" "${debs[@]}"
in_root apt-get install -y -q "${PACKAGES_I386[@]}"

# Flatpaks system-wide (Flathub is set up by softglowos-apps)
in_root flatpak install --system --noninteractive -y flathub "${FLATPAKS[@]}"

# Live session: German, our user name and host name (the installed system
# gets its own from Calamares)
cat > "$ROOT/etc/casper.conf" <<'EOF'
export USERNAME="softglowos"
export USERFULLNAME="SoftglowOS Live"
export HOST="softglowos"
export BUILD_SYSTEM="Ubuntu"
export FLAVOUR="SoftglowOS"
EOF
printf 'LANG=de_DE.UTF-8\n' > "$ROOT/etc/default/locale"
sed -i 's/^XKBLAYOUT=.*/XKBLAYOUT="de"/' "$ROOT/etc/default/keyboard"

in_root update-initramfs -u -k all

### The NVIDIA drivers for the installer (softglowos-install-nvidia) ###

eval "$(grep -E '^(OPEN|CLOSED)=' "$ROOT/usr/libexec/softglowos-install-nvidia")"
in_root apt-get clean
for driver in "$OPEN-open:$OPEN" "$CLOSED:$CLOSED"; do
  in_root apt-get install -y -q --download-only "nvidia-driver-${driver%:*}" \
    "linux-modules-nvidia-${driver%:*}-generic" "libnvidia-gl-${driver#*:}:i386" >/dev/null
done
mkdir -p "$ISO/pool"
mv "$ROOT"/var/cache/apt/archives/*.deb "$ISO/pool/"
(cd "$ISO/pool" && apt-ftparchive packages . > Packages && gzip -k9 Packages &&
  apt-ftparchive release . > Release)

### Clean up ###

in_root apt-get clean
rm -rf "$ROOT/tmp/"* "$ROOT/var/tmp/"* "$ROOT/usr/sbin/policy-rc.d"
truncate -s 0 "$ROOT/etc/machine-id"
rm -f "$ROOT/var/lib/dbus/machine-id"
unmount_root

### The ISO ###

mkdir -p "$ISO/casper" "$ISO/.disk" "$ISO/boot/grub" "$ISO/EFI/boot"
cp "$ROOT"/boot/vmlinuz-* "$ISO/casper/vmlinuz"
cp "$ROOT"/boot/initrd.img-* "$ISO/casper/initrd"
in_root dpkg-query -W --showformat='${Package} ${Version}\n' > "$ISO/casper/filesystem.manifest"
du -sx --block-size=1 "$ROOT" | cut -f1 > "$ISO/casper/filesystem.size"
mksquashfs "$ROOT" "$ISO/casper/filesystem.squashfs" -comp zstd -Xcompression-level 15 \
  -noappend -quiet
echo "SoftglowOS $VERSION - Ubuntu 26.04 amd64 ($(date -u +%Y%m%d))" > "$ISO/.disk/info"

# Ubuntu's signed shim and GRUB: the CD build of GRUB finds the ISO through
# .disk/info and reads /boot/grub/grub.cfg
cp "$ROOT/usr/lib/shim/shimx64.efi.signed.latest" "$ISO/EFI/boot/bootx64.efi"
cp "$ROOT/usr/lib/shim/mmx64.efi" "$ISO/EFI/boot/mmx64.efi"
cp "$ROOT/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed" "$ISO/EFI/boot/grubx64.efi"
cat > "$ISO/boot/grub/grub.cfg" <<'EOF'
set timeout=5
set default=0
loadfont unicode
set menu_color_normal=white/black
set menu_color_highlight=black/light-gray

menuentry "SoftglowOS" {
  linux /casper/vmlinuz boot=casper quiet splash locale=de_DE.UTF-8 keyboard-configuration/layoutcode=de ---
  initrd /casper/initrd
}
menuentry "SoftglowOS (English)" {
  linux /casper/vmlinuz boot=casper quiet splash locale=en_US.UTF-8 keyboard-configuration/layoutcode=us ---
  initrd /casper/initrd
}
menuentry "SoftglowOS (sichere Grafik / safe graphics)" {
  linux /casper/vmlinuz boot=casper nomodeset quiet splash locale=de_DE.UTF-8 keyboard-configuration/layoutcode=de ---
  initrd /casper/initrd
}
EOF

# The EFI partition of the ISO, for booting from a USB stick
efi=$WORK/efi.img
mkfs.vfat -C -n SGEFI "$efi" 10240 >/dev/null
mmd -i "$efi" ::/EFI ::/EFI/boot
mcopy -i "$efi" "$ISO/EFI/boot/"* ::/EFI/boot/

mkdir -p /out
iso_file=/out/softglowos-ubuntu-$VERSION-amd64.iso
xorriso -as mkisofs -r -V "SoftglowOS" -J -joliet-long -l -iso-level 3 \
  -partition_offset 16 -append_partition 2 0xef "$efi" -appended_part_as_gpt \
  -e --interval:appended_partition_2:all:: -no-emul-boot \
  -o "$iso_file" "$ISO"
ls -lh "$iso_file"
