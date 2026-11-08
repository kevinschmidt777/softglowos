# Ubuntu port (prototype)

SoftglowOS is built on Bazzite GNOME (`main`). This branch (`ubuntu-base`)
builds a prototype of the same system on Ubuntu, so both can be compared on
real hardware before deciding on a base. `main` stays untouched.

Why: a lot of Linux software only ships as `.deb` (Ubuntu/Debian).

## Decisions

| Topic | Decision |
|---|---|
| Base | Ubuntu 26.04 LTS, GNOME on Wayland |
| Kernel | Ubuntu's stock kernel (HWE later). No gaming kernel: Secure Boot and NVIDIA rebuilds aren't worth the small gain |
| Build | Our parts as `.deb` packages, an apt repository, a live ISO |
| Packages | `softglowos-base`, `softglowos-hub`, `softglowos-rnnoise`, `softglowos-obs`, `softglowos-drivers`, `softglowos-gaming`, `softglowos-apps`, `softglowos-vendor-apps` |
| apt repository | GitHub Pages (`kevinschmidt777.github.io/softglowos`), a flat repository signed with `APT_SIGNING_KEY`, published by GitHub Actions from `ubuntu-base` |
| Updates | Plain apt. No atomic updates or rollback (the biggest loss compared to Bazzite) |
| Installer | Calamares with our branding, German with "du" |
| NVIDIA | Picked per card by `ubuntu-drivers`: open modules for RTX 20 and newer, the proprietary driver for older cards. Installed from the ISO during installation, offline |
| Intel / AMD | Same support as Bazzite: NVIDIA, AMD and Intel GPUs and CPUs. AMD and Intel run on the kernel drivers plus Mesa (32-bit too, for Steam). Encoding in OBS: VA-API for AMD, Quick Sync through `intel-media-va-driver-non-free` for Intel |
| Audio | Ubuntu's PipeWire and Mesa plus our PipeWire/WirePlumber config. Newer versions from PPAs only if the hardware test shows problems |
| Snap | Removed and pinned so apt can't bring it back |
| App store | Bazaar (Flathub), built by us as "Softglow Store" (own name, icon and texts; Bazaar's authors stay credited in the About dialog) with our home page and blocklist. GNOME Software stays hidden and only opens downloaded `.deb` files |
| Heroic, GoXLR Utility, Steam | Official `.deb`s (Heroic and GoXLR open source, Steam Valve's launcher like in Bazzite), mirrored into our apt repository on every build |
| Chrome, Discord | Their licenses don't allow redistribution, so neither is in the ISO or our repository. `softglowos-vendor-apps` fetches the official `.deb` once the computer is online: once per app (a removed app stays removed). Chrome then updates through Google's repository, Discord through our timer while it isn't running |
| Gaming | Steam, Lutris, MangoHud, vkBasalt, Gamemode, Bazzite's sysctl/zram/I/O-scheduler values. No sched_ext (scx) for now |
| Secure Boot | Stays on. Only signed kernel modules: Ubuntu's prebuilt NVIDIA and v4l2loopback modules, no DKMS. xone (Xbox wireless dongle) is left out for now, Ubuntu only has it as DKMS |
| Hub | Updates, channels, rollback and GPU image switching are hidden. GPU switching isn't needed on Ubuntu, one system covers every card |
| Later | DaVinci Resolve (davincibox via Distrobox), Hub update page on apt |

## What carries over

- The Hub, including the setup assistant, mixer, devices and lighting (GTK4/libadwaita, distro-independent)
- PipeWire/WirePlumber config, branding, wallpapers, GNOME extensions and settings, udev rules, StreamController plugins
- OBS (official PPA), GoXLR Utility (ships a `.deb`), OpenRGB, Chrome, Steam, Lutris

## What has to be redone

- `recipes/` and `files/scripts/` (BlueBuild, dnf) become Debian packaging
- The OBS plugins we build ourselves, now against Ubuntu's OBS
- The installer: Anaconda (`installer/`) becomes Calamares
- Hub helpers tied to rpm-ostree: `softglowos-update`, `-update-check`, `-switch-channel`, `-rebase`, `-gpu-check`, `-resolve`
- Bazzite pieces we rely on: Bazaar, the Terra repository (Discord, Heroic), davincibox

## Taken from Bazzite

From `ublue-os/bazzite` (`system_files/desktop/shared`, `build_files/bazzite`):

- sysctl: `kernel.split_lock_mitigate=0`, `vm.max_map_count=2147483642`,
  BBR + MTU probing, IPv6 temporary addresses, higher inotify limits
- zram: zstd, half the RAM, at most 16 GB
- I/O scheduler: kyber for SSD/NVMe, bfq for HDD and SD cards
- NVIDIA: the power saving options (`nvidia-power.conf`, `nvidia-deck.conf`),
  `80-nvidia-pm.rules` (removes the card's USB controllers) and
  `nvidia-persistenced` off. `nvidia-powerd` is on in Ubuntu already. Not
  taken: mutter's `kms-modifiers`, which GNOME 50 already uses for NVIDIA;
  set for every card, it would force them on the older Intel GPUs mutter
  leaves out on purpose

Bazzite's WirePlumber (Terra's `terra-wireplumber`) is upstream WirePlumber
with a single OpenGamingCollective patch: `wpctl clear-default` does nothing
when Steam runs it, so Steam can't reset the chosen output device (our
monitor mix follows it). It doesn't touch latency. We keep Ubuntu's
WirePlumber and divert `wpctl` to a small wrapper in `softglowos-base` that
blocks only that call.

## Building

`ubuntu/build.sh [package…]` builds the packages in an Ubuntu 26.04
container into `ubuntu/out/`. Each package in `ubuntu/packages/` has a
`DEBIAN/` folder, an optional `root/` with Ubuntu-only files and an optional
`stage.sh` that takes the shared files from `files/` and `apps/`.

`softglowos-base` swaps Ubuntu's session, Yaru and dock for plain GNOME with
our extensions (pinned in `extensions.list`), Geist, wallpapers, boot splash,
login logo, the GNOME defaults Bazzite gave us, and our PipeWire/WirePlumber
config. `softglowos-refresh` rebuilds `os-release` and the GNOME overlays
(donate banner, microphone indicator) after every apt run, because unlike the
image those come from packages that update on their own.

`softglowos-hub` builds the Hub with meson and leaves out the helpers for
image updates, image switching by graphics card and Resolve; the Hub hides
those features when their helpers are missing. `softglowos-rnnoise` builds
RNNoise's LADSPA plugin from source per architecture. `softglowos-base`
depends on it: without the plugin PipeWire can't load the mixer's
filter-chain and doesn't start at all.

The ISO's bootloader needs `quiet splash` on the kernel command line, or the
boot splash never shows.

`softglowos-obs` takes OBS from the OBS team's PPA (Ubuntu's OBS has no
browser source) and builds every plugin of the Bazzite image against it,
with the same pinned versions (`files/scripts/build-obs-plugins.sh`) plus
obs-vkcapture and DroidCam. OBS's app entry is diverted and rebuilt by
`softglowos-refresh` from `desktop-tweaks/`, so it starts `softglowos-obs`
and prefers the strong GPU, and keeps doing so after OBS updates.

`softglowos-drivers` holds what AMD, Intel and NVIDIA need: Mesa, firmware,
Intel's Quick Sync runtime, `switcheroo-control`, `ubuntu-drivers` and the
NVIDIA settings from Bazzite. The NVIDIA driver itself is installed by the
ISO with `ubuntu-drivers`, which takes Ubuntu's signed prebuilt modules. The
OBS virtual camera's v4l2loopback module comes signed with Ubuntu's kernel
(`linux-image-generic` depends on it), so OBS doesn't need DKMS.

`softglowos-gaming` takes Valve's Steam launcher (`steam-launcher`, like
Bazzite ships it: Steam's icon and app entry are there from the start, no
"Install Steam" step as with Ubuntu's `steam-installer`) plus Ubuntu's
`steam-libs`, and Lutris, Gamemode, MangoHud, vkBasalt, Gamescope,
Protontricks and Winetricks from the archive and Bazzite's system values.
`fetch-mirrored.sh` puts Valve's package into our repository; once
installed it adds Valve's repository and updates from there. Valve's
launcher pulls in XTerm, which stays out of the app grid. The Game Capture
variable (`OBS_VKCAPTURE=1`) sits in a wrapper diverted over
`/usr/bin/steam`, so it also applies when Steam starts from an app entry of
its own in the home folder; Lutris and Heroic get it in their app entries. The 32-bit parts (Steam's
libraries, Mesa, Gamemode and NVIDIA's GL library for the installed driver)
come with the ISO, which enables i386. Ubuntu has no 32-bit MangoHud or
vkBasalt, so those only work in 64-bit games.

`softglowos-apps` sets up StreamController (Flatpak from Flathub, installed
by the ISO) with our mixer plugin and its OBS plugin, the GoXLR Utility
daemon, OpenRGB and Flathub.

`softglowos-store` builds Bazaar from source as Softglow Store (see the
decisions table).

## The ISO

`ubuntu/iso/build.sh` builds the live ISO in a privileged Ubuntu container
(the `iso` job of the package workflow, started by hand): debootstrap,
our packages with everything they recommend, the GNOME apps Bazzite ships
(as Ubuntu packages, the rest as Flatpaks), casper for the live boot, a
squashfs, and Ubuntu's signed shim and GRUB, so it boots with Secure Boot.
UEFI only. The live session is German by default (English in the boot menu)
and opens the installer.

`softglowos-installer` only exists in the live system: Calamares with our
branding, ext4 by default, no swap (zram), and Ubuntu's signed NVIDIA driver
from the ISO's pool for NVIDIA cards (`softglowos-install-nvidia`: the open
driver where the card supports it, the proprietary 580 for older cards).
While it's installed, the setup assistant, crash reports and the Chrome/
Discord timer are off; Calamares removes it, together with Calamares and
casper, from the installed system, which turns them back on.

The packages target x86_64. On Apple Silicon, Ubuntu 26.04's tar doesn't
work under Rosetta at all, and under QEMU only packing fails, so the x86_64
builds run on GitHub (`.github/workflows/ubuntu-packages.yml`, branch
`ubuntu-base`), which also installs them on a stock Ubuntu 26.04 and checks
OBS's plugins. `PLATFORM=linux/arm64 ubuntu/build.sh` builds the
architecture-independent packages for the arm64 test VM locally.

## Testing

1. Basics in the VM
2. A/B test on the gaming PC from the external SSD: audio delay (capture card,
   GoXLR), NVENC and Quick Sync in OBS, look and dock, installer and setup
   assistant, games
