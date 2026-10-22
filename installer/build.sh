#!/usr/bin/bash
# Turns the SoftglowOS image into the live system of the ISO (see
# Containerfile): a signed kernel and a live initramfs, Anaconda with our
# branding that opens on its own, and both images to install in the container
# storage (softglowos-live-payload picks one by the graphics card). Follows Bazzite's live ISO (github.com/ublue-os/bazzite,
# installer/), which builds on the same base.
set -exo pipefail

REGISTRY=${REGISTRY:?}
TAG=${TAG:?}
SRC=/src
BRANDING=/usr/share/softglowos/branding

# Bazzite pins its packages; the live system needs other ones
dnf -qy versionlock clear || :

### Kernel ###

# Bazzite's kernel is signed with Universal Blue's key, which Secure Boot
# only accepts after enrolling it, so the live system boots Fedora's kernel
dnf -y remove --setopt=protect_running_kernel=False \
  kernel kernel-core kernel-devel kernel-devel-matched kernel-modules kernel-modules-core kernel-modules-extra
rm -rf /usr/lib/modules/*
dnf -y --repo fedora,updates --setopt=tsflags=noscripts install kernel kernel-core
kernel=$(find /usr/lib/modules -mindepth 1 -maxdepth 1 -type d -printf '%P\n')
depmod "$kernel"
# GSP firmware for NVIDIA cards on nouveau
dnf -qy install nvidia-gpu-firmware || :

dnf -qy install dracut-live
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
  --add "dmsquash-live dmsquash-live-autooverlay" \
  "/usr/lib/modules/$kernel/initramfs.img" "$kernel"

### The images to install ###

mkdir -p "$(realpath /root)"
podman pull "$REGISTRY/softglowos:$TAG" "$REGISTRY/softglowos-nvidia:$TAG"
printf 'REGISTRY=%s\nTAG=%s\n' "$REGISTRY" "$TAG" >/usr/share/softglowos/live-images

### Live session ###

dnf -qy install livesys-scripts
sed -i 's/^livesys_session=.*/livesys_session=gnome/' /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service

# Nothing that belongs to an installed system: updates, the setup assistant,
# crash reports, the graphics driver switch, Stream Deck setup, Flatpaks
# from the internet. The Hub with its mixer and the GoXLR daemon stay.
for unit in rpm-ostree-countme.service rpm-ostreed-automatic.timer uupd.timer \
  bootloader-update.service ublue-system-setup.service bazzite-hardware-setup.service \
  ublue-hardware-setup.service bazzite-flatpak-manager.service ublue-flatpak-manager.service \
  flatpak-add-fedora-repos.service system-flatpak-setup.timer system-flatpak-setup.service \
  greenboot-set-rollback-trigger.service greenboot-healthcheck.service input-remapper.service \
  check-sb-key.service tailscaled.service; do
  systemctl disable "$unit" 2>/dev/null || :
done
for unit in softglowos-crash-reporter.service softglowos-gpu-check.service \
  softglowos-streamcontroller.service softglowos-update-check.timer bazzite-user-setup.service \
  ublue-user-setup.service user-flatpak-setup.timer podman-auto-update.timer; do
  systemctl --global disable "$unit" 2>/dev/null || :
done
rm -f /etc/xdg/autostart/com.softglowos.Hub.Setup.desktop

### Installer ###

dnf -qy install anaconda-live anaconda-webui firefox libblockdev-{btrfs,lvm,dm}
mkdir -p /var/lib/rpm-state  # Anaconda's web UI needs it

cat >>/usr/share/anaconda/interactive-defaults.ks <<EOF
# The image for this graphics card, written on boot by softglowos-live-payload
%include /run/softglowos/install.ks

# A fixed name: without one, NetworkManager takes whatever the router still
# knows for this address, which is the live system's localhost-live
network --hostname=softglowos

# Secure Boot: the kernel is signed with Universal Blue's key. Enrolling it
# is confirmed on the next start (MOK manager, password universalblue).
%post --nochroot
[ -d /sys/firmware/efi ] || exit 0
mokutil --timeout -1 || :
printf 'universalblue\nuniversalblue\n' | mokutil --import /usr/share/softglowos/secure-boot.der || :
LC_ALL=C mokutil --sb-state | grep -q 'SecureBoot enabled' || exit 0
run0 --user=liveuser zenity --info --title='Secure Boot' --width=480 --text="\$(cat /usr/share/softglowos/secure-boot.txt)" || :
%end

# Bluetooth mice and keyboards paired in the live system (softglowos-live-pairing)
# work at the installed system's login screen too
%post --nochroot
[ -d /var/lib/bluetooth ] && [ -d "\$ANA_INSTALL_PATH/var" ] || exit 0
mkdir -p "\$ANA_INSTALL_PATH/var/lib/bluetooth"
cp -a /var/lib/bluetooth/. "\$ANA_INSTALL_PATH/var/lib/bluetooth/"
%end

# Installed: closing the installer restarts the computer (softglowos-installer)
%post --nochroot
touch /run/softglowos/installed
%end
EOF
curl -fsSL --retry 3 -o /usr/share/softglowos/secure-boot.der \
  https://github.com/ublue-os/akmods/raw/main/certs/public_key.der
cat >/usr/share/softglowos/secure-boot.txt <<'EOF'
<b>One more step after the restart</b>
A blue screen appears: choose "Enroll MOK", "Continue", "Yes", type <b>universalblue</b> and choose "Reboot".

<b>Ein Schritt noch nach dem Neustart</b>
Ein blauer Bildschirm erscheint: "Enroll MOK", "Continue", "Yes" wählen, <b>universalblue</b> eintippen und "Reboot" wählen.
EOF

# Our installer opens right away instead of Fedora's welcome screen
sed -i 's/^\[Desktop Entry\]/[Desktop Entry]\nHidden=true/' \
  /usr/share/anaconda/gnome/org.fedoraproject.welcome-screen.desktop || :

# "Restart system" as the finish button, "du" in German (patch-webui.py)
python3 "$SRC/patch-webui.py" "$SRC/webui-de-du.json"

### Branding ###

cp -a "$SRC/system_files/." /
systemctl enable softglowos-live-payload.service softglowos-live-keyboard.service \
  softglowos-live-splash.service
# The dock's installer icon restarts after installing as well
sed -i 's|^Exec=\(/usr/bin/\)\?liveinst|Exec=/usr/libexec/softglowos-installer|' \
  /usr/share/applications/*.desktop
dnf -qy install librsvg2-tools
# Anaconda shows the logo as a 2rem square on the teal header: our symbol in white
sed 's/#2e3436/#ffffff/g' "$BRANDING/logo-symbolic.svg" |
  rsvg-convert -h 96 -o /usr/share/cockpit/branding/fedora/logo.png
for size in 48x48 scalable; do
  mkdir -p "/usr/share/icons/hicolor/$size/apps"
done
rsvg-convert -h 48 /usr/share/icons/hicolor/scalable/places/softglowos-logo.svg \
  -o /usr/share/icons/hicolor/48x48/apps/org.fedoraproject.AnacondaInstaller.png
cp /usr/share/icons/hicolor/scalable/places/softglowos-logo.svg \
  /usr/share/icons/hicolor/scalable/apps/org.fedoraproject.AnacondaInstaller.svg
mkdir -p /usr/share/icons/hicolor/symbolic/apps
cp "$BRANDING/logo-symbolic.svg" \
  /usr/share/icons/hicolor/symbolic/apps/org.fedoraproject.AnacondaInstaller-symbolic.svg
rm -f /usr/share/icons/hicolor/48x48/apps/org.fedoraproject.AnacondaInstaller.svg
gtk-update-icon-cache -f /usr/share/icons/hicolor || :
glib-compile-schemas /usr/share/glib-2.0/schemas

### ISO layout (Titanoboa) ###

dnf -qy install grub2-efi-x64-cdboot
mkdir -p /boot/efi
cp -a /usr/lib/efi/*/*/EFI /boot/efi/
mkdir -p /usr/lib/bootc-image-builder
cp "$SRC/iso.yaml" /usr/lib/bootc-image-builder/iso.yaml

rm -f /etc/localtime
systemd-firstboot --timezone UTC

# The live root is an overlay in /run, too small for unpacking the image
rm -rf /var/tmp
mkdir /var/tmp
cat >/etc/systemd/system/var-tmp.mount <<'EOF'
[Unit]
Description=Larger tmpfs for /var/tmp on the live system

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=50%%,nr_inodes=1m

[Install]
WantedBy=local-fs.target
EOF
systemctl enable var-tmp.mount

dnf clean all

# Last, since dnf reads the Fedora release from it: the installer names the
# SoftglowOS version instead of Fedora's (live system only)
version=$(cat /usr/share/softglowos/version)
sed -i "s/^VERSION_ID=.*/VERSION_ID=\"$version\"/; s/^VERSION=.*/VERSION=\"$version\"/" /usr/lib/os-release
