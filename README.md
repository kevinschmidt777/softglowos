# Streamer OS

> Working title. Early prototype, not ready for daily use.

A Linux desktop for gamers and Twitch streamers that works out of the box:
native OBS, GoXLR, Stream Deck and audio routing without the usual fiddling.
It is built as a custom [Bazzite](https://bazzite.gg) GNOME image with
[BlueBuild](https://blue-build.org), so updates are atomic and can be rolled back.

## What's in the prototype (v0)

- Based on `bazzite-gnome-nvidia-open` (NVIDIA RTX 20 series and newer). An AMD/Intel variant follows.
- **OBS Studio as a native RPM** instead of the Flatpak.
- **GoXLR Utility daemon** running in the background (tray disabled; our own mixer will be the UI).
- Mac-style **dock at the bottom**, always visible, and window buttons on the right.
- **Automatic light/dark theme** by time of day (Night Theme Switcher).
- Placeholder branding: name, wallpapers, boot splash and login logo.

## Repository layout

| Path | Purpose |
|---|---|
| `recipes/recipe.yml` | The image recipe: base image and all modules |
| `files/system/` | Files copied 1:1 into the image root |
| `files/gschema-overrides/` | GNOME default settings |
| `files/scripts/` | Build-time scripts |
| `disk_config/` | Settings for the ISO and the qcow2 VM disk |
| `.github/workflows/` | Image build (on push and daily) and disk image build (manual) |

## Building

Every push to `main` builds the image and publishes it to
`ghcr.io/kevinschmidt777/streamer-os`, signed with cosign.

The ISO and a ready-to-boot qcow2 VM disk are built by the **Build disk images**
workflow, started manually:

```bash
gh workflow run build-disk.yml
```

The qcow2 disk ships a throwaway test user (`tester` / `streamer`) because Bazzite
has no first-boot account setup. Only use it in a VM.

## Switching an existing Bazzite install

```bash
sudo bootc switch ghcr.io/kevinschmidt777/streamer-os:latest
```

## Verification

```bash
cosign verify --key cosign.pub ghcr.io/kevinschmidt777/streamer-os
```
