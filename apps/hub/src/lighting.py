"""RGB lighting through OpenRGB (no GTK here, softglowos-lighting-save uses
it too).

The user service softglowos-lighting runs the OpenRGB server, reachable
from this computer only. It starts once the Hub's Lighting page is opened
and with every login after the first change there. The current state is
kept as the OpenRGB profile "SoftglowOS": saved after every change in the
Hub and when the service stops (so changes made in the OpenRGB app stay
too), loaded when it starts. Before anyone touches the lighting, it stays
as the hardware has it."""

import json
import subprocess
import time
from pathlib import Path

from openrgb import OpenRGBClient
from openrgb.utils import ModeColors, ModeFlags, RGBColor

SERVICE = 'softglowos-lighting.service'
PROFILE = 'SoftglowOS'
CLIENT_NAME = 'SoftglowOS Hub'
SETTINGS_FILE = Path.home() / '.config' / 'softglowos' / 'lighting.json'

DEFAULTS = {'on': True, 'effect': 'static', 'color': '#2190a4', 'brightness': 100}

# Effect -> OpenRGB mode names, best first. Devices without the effect light
# up statically in the chosen color.
EFFECT_MODES = {
    'static': ('static', 'direct'),
    'breathing': ('breathing',),
    'rainbow': ('rainbow wave', 'spectrum cycle', 'rainbow'),
}


def load_settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def start_service():
    subprocess.run(['systemctl', '--user', 'start', SERVICE], check=False)


def enable_service():
    """From the first change on, the lighting comes back with every login."""
    subprocess.run(['systemctl', '--user', 'enable', SERVICE], check=False,
                   stderr=subprocess.DEVNULL)


def connect(timeout=20):
    """Connects to the server and waits until device detection settles
    (the server answers before it found everything). Raises OSError when
    there's no server."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            client = OpenRGBClient(name=CLIENT_NAME)
            break
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)

    # Same device count three times in a row; with none found, give
    # detection a few more seconds
    started = time.monotonic()
    counts = []
    while time.monotonic() - started < 15:
        client.update()
        counts.append(len(client.devices))
        if len(counts) >= 3 and len(set(counts[-3:])) == 1 and \
                (counts[-1] > 0 or time.monotonic() - started > 8):
            break
        time.sleep(1)
    return client


def effects(client):
    """The effects at least one device can do, in menu order."""
    return [effect for effect in EFFECT_MODES
            if effect == 'static' or any(_mode(device, effect) for device in client.devices)]


def apply(client, settings):
    for device in client.devices:
        try:
            _apply_device(client, device, settings)
        except Exception as error:  # one odd device mustn't stop the others
            print(f'Lighting: {device.name}: {error}')


def save_profile(client):
    client.save_profile(PROFILE)


def _mode(device, effect):
    for name in EFFECT_MODES[effect]:
        for mode in device.modes:
            if mode.name.lower() == name:
                return mode
    return None


def _apply_device(client, device, settings):
    if not settings['on']:
        off = next((mode for mode in device.modes if mode.name.lower() == 'off'), None)
        if off:
            device.set_mode(off)
        else:
            device.off()
        return

    mode = _mode(device, settings['effect']) or _mode(device, 'static')
    if mode is None:
        device.set_custom_mode()
        mode = device.modes[device.active_mode]

    brightness = settings['brightness'] / 100
    color = RGBColor.fromHEX(settings['color'])
    color = RGBColor(*(round(value * brightness) for value in (color.red, color.green, color.blue)))

    if mode.color_mode == ModeColors.MODE_SPECIFIC:
        mode.colors = [color] * mode.colors_max
    elif mode.color_mode in (ModeColors.NONE, ModeColors.RANDOM) and \
            ModeFlags.HAS_BRIGHTNESS in mode.flags and client.protocol_version >= 3:
        # Effects without a color of ours (rainbow) dim through the mode
        low, high = mode.brightness_min, mode.brightness_max
        mode.brightness = round(low + (high - low) * brightness)
    device.set_mode(mode)
    if mode.color_mode == ModeColors.PER_LED:
        device.set_color(color, fast=True)
