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
| Packages | `softglowos-base`, `softglowos-hub`, `softglowos-obs`, `softglowos-drivers`, `softglowos-gaming` |
| apt repository | GitHub Pages, signed, filled by GitHub Actions |
| Updates | Plain apt. No atomic updates or rollback (the biggest loss compared to Bazzite) |
| Installer | Calamares with our branding, German with "du" |
| NVIDIA | Picked per card by `ubuntu-drivers`: open modules for RTX 20 and newer, the proprietary driver for older cards. Installed from the ISO during installation, offline |
| Intel / AMD | Same support as Bazzite: NVIDIA, AMD and Intel GPUs and CPUs. AMD and Intel run on the kernel drivers plus Mesa (32-bit too, for Steam). Encoding in OBS: VA-API for AMD, Quick Sync through `intel-media-va-driver-non-free` for Intel |
| Audio | Ubuntu's PipeWire and Mesa plus our PipeWire/WirePlumber config. Newer versions from PPAs only if the hardware test shows problems |
| Snap | Removed and pinned so apt can't bring it back |
| App store | Bazaar (Flathub), built by us with our home page and blocklist. GNOME Software stays hidden and only opens downloaded `.deb` files |
| Discord, Heroic | Official `.deb`s, mirrored into our apt repository daily so they update with the system |
| Gaming | Steam, Lutris, MangoHud, vkBasalt, Gamemode, xone, Bazzite's sysctl/zram/I/O-scheduler values. No sched_ext (scx) for now |
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
- Kernel modules via DKMS: `v4l2loopback` (OBS virtual camera), `xone` (Xbox wireless dongle)

Bazzite's WirePlumber (Terra's `terra-wireplumber`) is upstream WirePlumber
with a single OpenGamingCollective patch: `wpctl clear-default` does nothing
when Steam runs it, so Steam can't reset the chosen output device (our
monitor mix follows it). It doesn't touch latency. We keep Ubuntu's
WirePlumber and divert `wpctl` to a small wrapper in `softglowos-base` that
blocks only that call.

## Testing

1. Basics in the VM
2. A/B test on the gaming PC from the external SSD: audio delay (capture card,
   GoXLR), NVENC and Quick Sync in OBS, look and dock, installer and setup
   assistant, games
