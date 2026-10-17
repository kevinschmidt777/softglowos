# Design system

How SoftglowOS looks, feels and sounds. This applies to the shell, the system
defaults and every app we build (Hub, mixer, setup assistant).

## Principles

- **Apple-clean.** Calm, neutral and spacious. Gray surfaces carry the UI and color
  is only an accent. Gaming shows in the features, not in RGB.
- **One system, not two.** We build on GNOME's libadwaita and only define what is
  truly ours. Third-party GNOME apps and our own apps must look like they belong together.
- **Light and dark are equal.** The theme switches by time of day, so both modes
  get the same care. Never design one mode and derive the other.
- **Nothing gets in the way of a stream.** No system sounds, no surprise popups,
  no effects that cost performance.

## Foundation: libadwaita

Neutral colors, status colors (success, warning, error), the type scale, spacing,
corner radii and shadows all come from libadwaita. Our apps use libadwaita's named
colors and style classes instead of hard-coded values, so they follow the accent
color and light/dark mode automatically.

Only the items below are ours.

## Color

| Token | Value | Notes |
|---|---|---|
| Accent | GNOME `teal` (`#2190a4`) | Set as the system accent, so third-party apps use the exact same tone |
| Everything else | libadwaita defaults | Window, view, sidebar, card and status colors |

Do not introduce a second brand color in the UI. Violet is off-limits: Twitch and
Bazzite both use it, so it would make us look like an offshoot.

## Typography

| Use | Font |
|---|---|
| Interface, documents, titles | **Geist** (SIL Open Font License) |
| Terminal, code, numbers in meters | **Geist Mono** |

Sizes and weights follow libadwaita's type scale (`title-1` to `title-4`,
`heading`, `body`, `caption`). The default UI size is 11 pt and window titles use
Geist Medium.

## Shape and spacing

- Corner radii follow libadwaita: windows and cards are rounded around 12 px,
  buttons and entries a bit less. We never override them, so our apps match
  third-party apps.
- Spacing follows libadwaita's 6 px grid.
- Density is GNOME's default: spacious and easy to hit, like macOS.

## Surfaces and glass

- Top bar, dock and popups are lightly translucent with blur (Blur my Shell).
- Window content stays solid for legibility and performance.

## Motion

- GNOME's default animations: fast and fluid.
- No decorative effects. Bazzite's magic lamp minimize effect is turned off.

## Sound

- All system sounds are off (event and input feedback sounds), so nothing beeps
  into a microphone or a stream.

## Icons

- Adwaita symbolic icons for UI elements, colorful app icons as shipped by apps.
- Our own apps get their own icons later, in the same style as GNOME app icons.

## Shell layout

| Element | Behavior |
|---|---|
| Top bar, left | Logo menu (system actions, settings, restart, power) instead of "Activities" |
| Top bar, right | Clock and status icons |
| Dock | Bottom, always visible, icons magnify on hover (Dash2Dock Animated) |
| Window buttons | Right side: minimize, maximize, close |
| Startup | Desktop, not the overview |
| Light/dark | Automatic by time of day (Night Theme Switcher) |

## Limits of theming

libadwaita apps we do not control (Files, Settings and so on) only take the accent
color, the light/dark mode and the fonts from us. They do not take custom radii,
colors or components. That is the main reason this design system stays close to
libadwaita.

## Open

- Final name, logo and wallpapers (everything is a placeholder for now).
- Own system sounds may be added later as part of the branding, still off by default.
