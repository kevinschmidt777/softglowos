"""RGB lighting through OpenRGB, plus the GoXLR through its own daemon (no
GTK here, softglowos-lighting-save and -login use it too).

The user service softglowos-lighting runs the OpenRGB server, reachable
from this computer only. It starts once the Hub's Lighting page is opened
and with every login after the first change there. The current state is
kept as the OpenRGB profile "SoftglowOS": saved after every change in the
Hub and when the service stops (so changes made in the OpenRGB app stay
too), loaded when it starts. Devices the profile doesn't know yet (built in
since) get the Hub's settings after the login. Before anyone touches the
lighting, it stays as the hardware has it.

Zones like ARGB headers can't tell how many LEDs hang on them and start
with none; they get their maximum, so one color reaches every LED without
setting them up in OpenRGB (sizes set there stay)."""

import colorsys
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from openrgb import OpenRGBClient, orgb
from openrgb.utils import ModeColors, ModeFlags, RGBColor

SERVICE = 'softglowos-lighting.service'
PROFILE = 'SoftglowOS'
CLIENT_NAME = 'SoftglowOS Hub'
SETTINGS_FILE = Path.home() / '.config' / 'softglowos' / 'lighting.json'

DEFAULTS = {'on': True, 'effect': 'static', 'color': '#2190a4', 'brightness': 100,
            'devices': []}

# Effect -> OpenRGB mode names, best first. Devices without the effect light
# up statically in the chosen color. Breathing is gone: every maker names it
# differently and many devices can't do it.
EFFECT_MODES = {
    'static': ('static', 'direct'),
    'rainbow': ('rainbow wave', 'spectrum cycle', 'rainbow'),
}

GOXLR_API = 'http://localhost:14564/api/'
GOXLR_UTILITY_URL = 'http://localhost:14564/'
GOXLR_MUTE_BUTTONS = ('Fader1Mute', 'Fader2Mute', 'Fader3Mute', 'Fader4Mute')
GOXLR_FADERS = ('A', 'B', 'C', 'D')

# openrgb-python drops a zone's size limits; keep them for _fill_empty_zones()
_zone_update = orgb.Zone._update


def _keep_size_limits(zone, data):
    _zone_update(zone, data)
    zone.leds_max = data.leds_max


orgb.Zone._update = _keep_size_limits


def load_settings():
    try:
        settings = {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)
    if settings['effect'] not in EFFECT_MODES:
        settings['effect'] = 'static'  # was breathing
    return settings


def save_settings(settings):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def start_service():
    # connect() waits for the server, so no need to wait for the start here
    subprocess.run(['systemctl', '--user', 'start', '--no-block', SERVICE], check=False)


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
    _fill_empty_zones(client)
    return client


def _fill_empty_zones(client):
    filled = False
    for device in client.devices:
        for zone in device.zones:
            if not zone.leds and getattr(zone, 'leds_max', 0) > 0:
                zone.resize(zone.leds_max)  # the server keeps the size
                filled = True
    if filled:
        client.update()


def effects(client):
    """The effects at least one device can do, in menu order."""
    return [effect for effect in EFFECT_MODES
            if effect == 'static' or goxlr_count()
            or any(_mode(device, effect) for device in client.devices)]


def apply(client, settings, devices=None):
    """Applies the settings to all devices, or only to the given ones."""
    for device in devices if devices is not None else client.devices:
        try:
            _apply_device(client, device, settings)
        except Exception as error:  # one odd device mustn't stop the others
            print(f'Lighting: {device.name}: {error}')


def save_profile(client, settings=None):
    """Saves the profile and notes which devices it holds."""
    client.save_profile(PROFILE)
    if settings is not None:
        settings['devices'] = [_device_id(device) for device in client.devices]


def apply_to_new(client, settings):
    """Gives devices the profile doesn't hold yet the Hub's settings.
    True if there were any. Nothing before the first change in the Hub."""
    known = set(settings['devices'])
    if not known:
        return False
    new = [device for device in client.devices if _device_id(device) not in known]
    if new:
        apply(client, settings, new)
    return bool(new)


def _device_id(device):
    return f'{device.name}|{device.metadata.location}'


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


# The GoXLR's lighting, through the GoXLR Utility daemon's HTTP API

def _goxlr_request(path, data=None):
    request = urllib.request.Request(
        GOXLR_API + path, data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read() or 'null')


def _goxlr_mixers():
    try:
        return _goxlr_request('get-devices').get('mixers') or {}
    except (OSError, ValueError):
        return {}  # no daemon, no GoXLR


def goxlr_count():
    return len(_goxlr_mixers())


def apply_goxlr(settings):
    """Static: everything in the color. Rainbow: the GoXLR's own rainbow
    animation where its firmware has one, else a rainbow across the faders
    that stands still. Off: everything dark. Kept in the GoXLR profile."""
    for serial, mixer in _goxlr_mixers().items():
        def command(name, *args):
            _goxlr_request('command', {'Command': [serial, {name: args[0] if len(args) == 1
                                                            else list(args)}]})
        try:
            animated = mixer['lighting']['animation']['supported']
            rainbow = settings['on'] and settings['effect'] == 'rainbow'
            if animated:
                command('SetAnimationMode', 'RainbowBright' if rainbow else 'None')
            if not settings['on']:
                command('SetGlobalColour', '000000')
            elif not rainbow:
                command('SetGlobalColour', _hex(settings['color'], settings['brightness']))
            elif not animated:
                for index, (fader, button) in enumerate(zip(GOXLR_FADERS, GOXLR_MUTE_BUTTONS)):
                    hue = index / len(GOXLR_FADERS)
                    color = _hex('#{:02x}{:02x}{:02x}'.format(
                        *(round(v * 255) for v in colorsys.hsv_to_rgb(hue, 1, 1))),
                        settings['brightness'])
                    command('SetFaderColours', fader, color, color)
                    command('SetButtonColours', button, color, None)
            command('SaveProfile')
        except (OSError, ValueError, KeyError) as error:
            print(f'Lighting: GoXLR {serial}: {error}')


def _hex(color, brightness):
    """'#2190a4' at 50 % -> '104852', the way the GoXLR wants it."""
    color = RGBColor.fromHEX(color)
    return '{:02X}{:02X}{:02X}'.format(
        *(round(value * brightness / 100) for value in (color.red, color.green, color.blue)))
