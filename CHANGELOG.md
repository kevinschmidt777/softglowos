# Changelog

All notable changes to SoftglowOS are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and SoftglowOS adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
new features raise the minor version, fixes raise the patch version. The
current version is in [`VERSION`](VERSION).

## [Unreleased]

## [1.1.1] - 2026-11-10

### Fixed

- With a GoXLR, the Stream-Mix in OBS didn't follow the mixer: a channel at
  full volume in the Hub could still be quiet in the stream (and in the
  headphones). PipeWire gave the GoXLR's channels a volume of its own (40 %
  for new devices), on top of the GoXLR's faders. The Hub now keeps them at
  100 %, so the faders alone set the volume.
- With a GoXLR, the single tracks for OBS (chat, music, system) stayed at
  full volume whatever the stream fader said. They now follow the stream
  faders and mutes, also when you move a fader on the desk.

## [1.1.0] - 2026-11-10

### Changed

- The mixer has exactly the channels of a GoXLR Mini now: microphone, chat,
  music and system. Game, browser and console are gone. Games, browsers and
  the capture card (console) play into system, which is everything you hear
  from the PC. Fewer channels, fewer ways for sound to get lost.
- The capture card's offset is the system offset now. An offset set for the
  console before carries over to system.
- OBS: tracks 2–5 are mic, chat, music and system. Existing scene
  collections are moved over on the next start of OBS: a game, browser or
  console source becomes "System" (the others go, so the PC sound isn't
  recorded twice). A copy of the old file stays next to it
  (`*.json.before-1.1.0`).
- Stream Deck keys set to game, browser or console now control system.

### Fixed

- With a GoXLR, the console (and the browser) could be silent in the
  headphones while OBS recorded them fine. They went through the GoXLR's
  Sample channel, which the Hub never routed to the headphones and which
  sat behind two extra volume controls. That way is gone.

## [1.0.1] - 2026-11-08

### Added

- The computer's other internal disks (for example a data disk or the Windows
  drive) are mounted at login and show up in the Files sidebar right away,
  like drives in Windows. No more password prompt to open them. Removable
  drives, encrypted disks and the small Windows/EFI helper partitions are left
  alone.
- `CHANGELOG.md`.

### Fixed

- SoftglowOS didn't update itself and never said when a new version was
  out. Updates from the SoftglowOS repository (and Ubuntu's regular updates)
  now install automatically in the background, and a notification says when
  a new version is available or was installed.
- Hub → Settings → Updates shows the installed and the new version, what's
  new from this changelog and an "Update now" button (no password needed for
  administrators), followed by a restart button.
- The GoXLR's desk faders now default to Chat on fader B and Music on fader
  C (set once per GoXLR, changes in the Hub's mixer stay).
- Steam did nothing when started from the dock or the app grid. Valve's
  launcher refused to start under the name our Game Capture wrapper gave it
  ("Unknown Steam package 'steam.distrib'").
- Google Chrome was missing from the dock after a fresh installation. Chrome
  and Discord are now downloaded from Google and Discord during the
  installation when the computer is online, so they are in the dock on the
  first login. Without a network connection during installation, they are
  fetched 30 seconds after the first boot instead of up to 11 minutes later.
- Bluetooth could be switched off in the live system, so the pairing screen
  for Bluetooth mice and keyboards didn't work before the installer opened.
  Bluetooth is now on by default in the live and the installed system. The
  pairing screen switches it on itself and waits for a Bluetooth controller
  that shows up late instead of giving up right away.

## [1.0.0] - 2026-11-08

First release of SoftglowOS: a Linux desktop for gamers and Twitch streamers
that works out of the box, built on Ubuntu 26.04 LTS with GNOME.

### Added

- **Live ISO** for every graphics card: boots a German live desktop (English
  in the boot menu) and opens the installer (Calamares with SoftglowOS
  branding). Bluetooth mice and keyboards can be paired before it opens.
  NVIDIA cards get Ubuntu's signed driver from the ISO during installation.
  Secure Boot stays on. UEFI only.
- **The Hub**: our own app for the audio mixer (PipeWire and GoXLR, with audio
  routing and a mini mixer in the top bar), devices, software, lighting and
  settings, plus a setup assistant on the first login, bug reports and crash
  reports.
- **OBS Studio** from the OBS team's PPA with the browser source and our
  plugin set (vkcapture game capture, Move Transition, Source Record, Source
  Clone, Shaderfilter, Composite Blur, Advanced Masks, Stroke Glow Shadow),
  ready on first start with the GPU's hardware encoder and the mixer tracks.
- **StreamController** for the Stream Deck with our mixer plugin and the OBS
  plugin already connected; started on login when a Stream Deck is plugged
  in.
- **GoXLR Utility** daemon in the background, controlled from the Hub.
- **OpenRGB 1.1** for RGB lighting, with one color, effect and brightness for
  everything in Hub → Lighting.
- **Gaming**: Valve's Steam launcher, Heroic, Lutris, Gamemode, MangoHud,
  vkBasalt, Gamescope, Protontricks, Winetricks, and Bazzite's sysctl, zram
  and I/O scheduler values. Games started from Steam, Heroic or Lutris work
  with OBS Game Capture without extra launch options.
- **Google Chrome** and **Discord**, fetched from their vendors once the
  computer is online.
- **Softglow Store**: Bazaar (Flathub) as our own app store with a curated
  start page.
- **Desktop**: plain GNOME with a Mac-style dock at the bottom, a macOS-style
  top bar with the logo menu, Geist and Geist Mono as system fonts, GNOME's
  teal accent color, automatic light/dark theme by time of day and no system
  sounds.
- **Branding**: name, wallpapers, boot splash, login logo and `fastfetch` logo.
- **Updates** through our signed apt repository on GitHub Pages
  (`sudo apt update && sudo apt full-upgrade`).

[Unreleased]: https://github.com/kevinschmidt777/softglowos/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/kevinschmidt777/softglowos/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/kevinschmidt777/softglowos/releases/tag/v1.0.0
