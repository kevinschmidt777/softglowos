# SoftglowOS

> Early prototype, not ready for daily use.

A Linux desktop for gamers and Twitch streamers that works out of the box:
native OBS, GoXLR, Stream Deck and audio routing without the usual fiddling.
It is built on Ubuntu 26.04 LTS with GNOME: our parts are `.deb` packages in
our own apt repository, installed from our live ISO. How it's built and why
is in [docs/ubuntu-port.md](docs/ubuntu-port.md).

## What's in it

- **One live ISO for every graphics card:** boots a German live desktop (English in the boot menu) and opens the installer (Calamares, in our colors and with our logo). Bluetooth mice and keyboards can be paired before it opens. NVIDIA cards get Ubuntu's signed driver from the ISO during installation, the open modules for RTX 20 and newer, the proprietary driver for older cards. Secure Boot stays on.
- **The Hub:** our own app for the mixer (PipeWire and GoXLR, with audio routing and a mini mixer in the top bar), devices, software, lighting and settings, plus a setup assistant on the first login and the updates (what's new, update now).
- **OBS Studio** from the OBS team's PPA with the browser source and our plugins (game capture via vkcapture, Move Transition, Source Record, Source Clone, Shaderfilter, Composite Blur, Advanced Masks, Stroke Glow Shadow). Ready on first start: the graphics card's hardware encoder and the mixer as global audio (track 1 the Stream-Mix, tracks 2–5 mic, chat, music and system). Games started from Steam, Heroic or Lutris work with "Game Capture" right away.
- **StreamController** for the Stream Deck with our mixer plugin and its OBS plugin already connected to OBS.
- **GoXLR Utility** daemon in the background (the Hub is the interface).
- **OpenRGB 1.1** for the RGB lighting of most vendors; Hub → Lighting sets one color, effect and brightness for everything.
- **Gaming:** Valve's Steam launcher, Heroic, Lutris, Gamemode, MangoHud, vkBasalt, Gamescope, Protontricks, Winetricks, and Bazzite's sysctl, zram and I/O scheduler values.
- **Google Chrome** and **Discord**, fetched from their makers during installation, or right after the first boot if the computer was offline then (their licenses don't allow us to ship them).
- **Softglow Store:** Bazaar (Flathub) built as our own app store with our start page: Creator Tools, Chat & Community, Gaming, Music & Media, Office & Tools.
- Plain GNOME instead of Ubuntu's session: Mac-style **dock at the bottom** (open apps marked with a dash in the accent color), macOS-style **top bar** with the logo menu, window buttons on the right.
- **Geist** and **Geist Mono** as system fonts, GNOME's **teal** as the accent color, **automatic light/dark theme** by time of day, no system sounds.
- The computer's **other internal disks** (data disks, the Windows drive) are mounted at login and sit in the Files sidebar, without asking for the password.
- Branding: name, wallpapers, boot splash, login logo and `fastfetch` logo.

The look and feel is described in [DESIGN.md](DESIGN.md).

## Repository layout

| Path | Purpose |
|---|---|
| `ubuntu/packages/` | One folder per package: `DEBIAN/`, an optional `root/` with its own files and an optional `stage.sh` that takes the shared files and builds or downloads the rest |
| `ubuntu/build.sh` | Builds the packages in an Ubuntu 26.04 container into `ubuntu/out/` |
| `ubuntu/fetch-mirrored.sh` | Puts the official `.deb`s of Heroic, GoXLR Utility, Steam and OpenRGB into our apt repository |
| `ubuntu/iso/` | The live ISO (debootstrap, casper, Ubuntu's signed shim and GRUB, UEFI only) |
| `files/system/` | Shared files the packages install at the same paths (audio config, branding, wallpapers, udev rules, user services, StreamController plugin, store config) |
| `files/gschema-overrides/` | GNOME default settings |
| `apps/hub/` | The Hub (Python, GTK4/libadwaita, Meson); `run-in-vm.sh` builds and starts it in a test VM |
| `tools/` | Generators for the wallpapers, the store banners and the mixer's PipeWire config (output is committed); `sync-audio-to-vm.sh` copies the audio config into a test VM |
| `.github/workflows/ubuntu-packages.yml` | Builds and checks the packages, publishes the apt repository from `main`, builds the ISO when started by hand |
| `VERSION` | The SoftglowOS version (SemVer: new features raise the minor, fixes the patch number); every release gets a `v<version>` tag |
| `CHANGELOG.md` | What changed in every version (Keep a Changelog, in English) |

## Building

Every push to `main` that touches the packages builds them on GitHub,
installs them on a stock Ubuntu 26.04 to check them, and publishes them as
our apt repository on GitHub Pages
(`https://kevinschmidt777.github.io/softglowos/`, signed with
`APT_SIGNING_KEY`).

The live ISO is built by the same workflow, started by hand:

```bash
gh workflow run ubuntu-packages.yml -f iso=true
```

Locally, `ubuntu/build.sh [package…]` builds packages in Docker;
`PLATFORM=linux/arm64 ubuntu/build.sh` builds the architecture-independent
ones for an arm64 test VM.

## Updates

SoftglowOS keeps itself up to date: unattended-upgrades installs our
packages (and Ubuntu's regular updates) in the background, a notification
tells about every new version, and Hub → Settings → Updates shows what's
new (from `CHANGELOG.md`, published next to the apt repository) with an
"Update now" button. By hand it's apt like every other Ubuntu package:

```bash
sudo apt update && sudo apt full-upgrade
```
