# SoftglowOS

> Early prototype, not ready for daily use.

A Linux desktop for gamers and Twitch streamers that works out of the box:
native OBS, GoXLR, Stream Deck and audio routing without the usual fiddling.
It is built as a custom [Bazzite](https://bazzite.gg) GNOME image with
[BlueBuild](https://blue-build.org), so updates are atomic and can be rolled back.

## What's in the prototype (v0)

- Two images on top of Bazzite GNOME: `softglowos` for AMD and Intel graphics (`bazzite-gnome`) and `softglowos-nvidia` for NVIDIA RTX 20 / GTX 16 series and newer (`bazzite-gnome-nvidia-open`).
- **OBS Studio as a native RPM** instead of the Flatpak, with the browser source, game capture (vkcapture), VLC source, DroidCam and the x264 encoder. Games started from Steam, Heroic or Lutris work with OBS's "Game Capture" source right away.
- **GoXLR Utility daemon** running in the background (tray disabled; our own mixer will be the UI).
- **Google Chrome** as the default browser, **Discord** and the **Heroic Games Launcher**, all as native RPMs.
- **StreamController** for the Stream Deck, the one Flatpak we ship (there is no native package).
- **OpenRGB** as a native RPM for the RGB lighting of most vendors. The setup assistant will later detect RGB hardware and only show it when needed.
- Mac-style **dock at the bottom**, always visible, with Files, Chrome, OBS, Discord, Steam and the terminal; window buttons on the right.
- macOS-style **top bar**: logo menu on the left, clock and status icons on the right.
- **Geist** and **Geist Mono** as system fonts, GNOME's **teal** as the accent color.
- **Automatic light/dark theme** by time of day (Night Theme Switcher).
- **No system sounds**, so nothing beeps into a stream.
- No Bazzite welcome portal, announcements or Steam autostart; a short own terminal greeting (English/German) in teal.
- **Bazaar** (app store for Flatpaks) with our own start page: Creator Tools, Chat & Community, Gaming, Music & Media, Office & Tools. It doesn't offer Flatpaks of the apps we ship natively.
- Bazzite's own entries (docs, forum, portal, updater, Steam Big Picture) are hidden from the app grid, `ujust` lost the recipes that would break our setup, and `fastfetch` shows our logo.
- Placeholder branding: name, wallpapers, boot splash and login logo.

The look and feel is described in [DESIGN.md](DESIGN.md).

## Repository layout

| Path | Purpose |
|---|---|
| `recipes/common.yml` | All modules, shared by both images |
| `recipes/softglowos.yml`, `recipes/softglowos-nvidia.yml` | The two image recipes: name and base image |
| `files/system/` | Files copied 1:1 into the image root |
| `files/gschema-overrides/` | GNOME default settings |
| `files/scripts/` | Build-time scripts |
| `disk_config/` | Settings for the ISO and the qcow2 VM disk |
| `apps/hub/` | The Hub app (Python, GTK4/libadwaita, Meson): mixer for PipeWire and GoXLR; `run-in-vm.sh` builds and starts it in the Fedora dev VM |
| `tools/` | Generators for the wallpapers, the Bazaar banners and the mixer's PipeWire config (output is committed); `sync-audio-to-vm.sh` copies the audio config into the dev VM |
| `.github/workflows/` | Image build (on push and daily) and disk image build (manual) |

## Building

Every push to `main` builds both images and publishes them to
`ghcr.io/kevinschmidt777/softglowos` and `ghcr.io/kevinschmidt777/softglowos-nvidia`,
signed with cosign.

The ISO and a ready-to-boot qcow2 VM disk are built by the **Build disk images**
workflow, started manually:

```bash
gh workflow run build-disk.yml
```

Systems installed from the ISO only accept updates signed with our key.

The qcow2 disk ships a throwaway test user (`tester` / `streamer`) because Bazzite
has no first-boot account setup. Only use it in a VM.

## Switching an existing Bazzite install

```bash
# AMD/Intel graphics
sudo bootc switch ghcr.io/kevinschmidt777/softglowos:latest
# NVIDIA
sudo bootc switch ghcr.io/kevinschmidt777/softglowos-nvidia:latest
```

## Verification

```bash
cosign verify --key cosign.pub ghcr.io/kevinschmidt777/softglowos
```
