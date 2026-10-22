"""GoXLR support (full-size and Mini) through the GoXLR Utility daemon.

The daemon's WebSocket sends the whole device status once and then a JSON
Patch for every change, also when a fader on the desk moves, so the Hub and
the hardware stay in sync both ways. API: github.com/GoXLR-on-Linux/goxlr-utility
(wiki "The GoXLR Utility API").

How our mixer maps onto the GoXLR:
- game, chat, music, system: the GoXLR channel of the same name. Mix A (the
  hardware fader) feeds the headphones ("Me"), mix B the stream; both are
  linked, so a fader on the desk moves both and keeps their ratio.
- per-mix mute: the mute button of the desk fader the channel sits on, so
  its light shows it (its mute function follows which mixes are muted);
  channels without a desk fader mute through the GoXLR's routing
  (channel -> headphones / stream mix)
- browser and console: our own software faders; their sound reaches the
  GoXLR through its Sample channel, which we take out of the GoXLR's stream
  mix (the WirePlumber script adds them to ours instead) and out of its Chat
  Mic, so Discord doesn't hear them
- microphone: level, gate, compressor and EQ in hardware; RNNoise and the
  mic offset run in software, so either takes the raw mic out of the
  GoXLR's stream mix
"""
import json
import shutil
from pathlib import Path

import gi

gi.require_version('Soup', '3.0')

import pulsectl
from gi.repository import GLib, GObject, Soup

from .audio import PipeWireMixer

URL = 'ws://localhost:14564/api/websocket'
RECONNECT_SECONDS = 5

CHANNELS = {'game': 'Game', 'chat': 'Chat', 'music': 'Music', 'system': 'System',
            'mic': 'Mic'}
INPUTS = {'game': 'Game', 'chat': 'Chat', 'music': 'Music', 'system': 'System',
          'mic': 'Microphone'}
GOXLR_CHANNELS = ('game', 'chat', 'music', 'system')
SAMPLE_CHANNELS = ('browser', 'console')
# Where PulseAudio names the device of an output, to tell the GoXLR apart
GOXLR_DEVICE_KEYS = ('alsa.card_name', 'api.alsa.card.name', 'device.product.name')
MIC_MONITOR_VOLUME = 128  # half, when listening to yourself is switched on at 0
FADERS = ('A', 'B', 'C', 'D')
FADER_CHOICES = ('mic', 'game', 'chat', 'music', 'system')

FULL_EQ = ('31Hz', '63Hz', '125Hz', '250Hz', '500Hz', '1KHz', '2KHz', '4KHz', '8KHz', '16KHz')
MINI_EQ = ('90Hz', '250Hz', '500Hz', '1KHz', '3KHz', '8KHz')
EQ_RANGE_DB = 9

COMPRESSOR_OFF = 'Ratio1_0'
COMPRESSOR_ON = 'Ratio3_2'

# Mute function of a desk fader's button for (stream muted, headphones muted)
MUTE_FUNCTIONS = {(True, True): 'All', (True, False): 'ToStream', (False, True): 'ToPhones'}
# What a pressed mute button mutes of our two mixes, by its mute function
MUTED_MIXES = {'All': (True, True), 'ToStream': (True, False), 'ToStreams': (True, False),
               'ToPhones': (False, True)}

MIC_TYPES = ('Dynamic', 'Condenser', 'Jack')
MIC_GAIN_MAX_DB = 72
PROFILE_SUFFIX = '.goxlr'
MIC_PROFILE_SUFFIX = '.goxlrMicProfile'


def _to_goxlr(value):
    return round(value * 255 / 100)


def _from_goxlr(value):
    return round(value * 100 / 255)


def _apply_patch(document, operations):
    """Applies a JSON Patch (RFC 6902, the operations the daemon sends)."""
    for operation in operations:
        keys = [key.replace('~1', '/').replace('~0', '~')
                for key in operation['path'].split('/')[1:]]
        parent = document
        for key in keys[:-1]:
            parent = parent[int(key)] if isinstance(parent, list) else parent[key]
        last = keys[-1]
        if isinstance(parent, list):
            index = len(parent) if last == '-' else int(last)
            if operation['op'] == 'remove':
                del parent[index]
            elif operation['op'] == 'add':
                parent.insert(index, operation['value'])
            else:
                parent[index] = operation['value']
        elif operation['op'] == 'remove':
            parent.pop(last, None)
        else:
            parent[last] = operation['value']


class GoXLRClient(GObject.Object):
    """Connection to the daemon. Emits "changed" whenever the status changes."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self._session = Soup.Session()
        self._socket = None
        self._next_id = 1
        self.status = None
        self._connect()

    @property
    def mixer(self):
        """Status of the first connected GoXLR, or None."""
        mixers = (self.status or {}).get('mixers') or {}
        return next(iter(mixers.values()), None)

    @property
    def serial(self):
        mixers = (self.status or {}).get('mixers') or {}
        return next(iter(mixers), None)

    def command(self, name, *args):
        if self._socket is None or self.serial is None:
            return
        # One argument goes as is, none or several as a list ("SaveProfile()" -> [])
        value = args[0] if len(args) == 1 else list(args)
        self._send({'Command': [self.serial, {name: value}]})

    def _send(self, data):
        self._socket.send_text(json.dumps({'id': self._next_id, 'data': data}))
        self._next_id += 1

    def _connect(self):
        message = Soup.Message.new('GET', URL)
        self._session.websocket_connect_async(message, None, None,
                                              GLib.PRIORITY_DEFAULT, None,
                                              self._on_connected)

    def _on_connected(self, session, result):
        try:
            self._socket = session.websocket_connect_finish(result)
        except GLib.Error:
            GLib.timeout_add_seconds(RECONNECT_SECONDS, self._retry)
            return
        self._socket.connect('message', self._on_message)
        self._socket.connect('closed', self._on_closed)
        self._send('GetStatus')

    def _retry(self):
        self._connect()
        return GLib.SOURCE_REMOVE

    def _on_closed(self, _socket):
        self._socket = None
        self.status = None
        self.emit('changed')
        GLib.timeout_add_seconds(RECONNECT_SECONDS, self._retry)

    def _on_message(self, _socket, _type, data):
        try:
            message = json.loads(data.get_data().decode())
        except (ValueError, UnicodeDecodeError):
            return
        response = message.get('data')
        if not isinstance(response, dict):
            return
        if 'Status' in response:
            self.status = response['Status']
        elif 'Patch' in response and self.status is not None:
            try:
                _apply_patch(self.status, response['Patch'])
            except (KeyError, IndexError, ValueError, TypeError):
                self._send('GetStatus')  # out of sync, start over
                return
        else:
            return
        self.emit('changed')


class Mixer(PipeWireMixer):
    """The Hub's mixer: PipeWire alone, or PipeWire plus a GoXLR when one is
    connected. Same interface either way, so the page doesn't care."""

    def __init__(self):
        super().__init__()
        self.goxlr = GoXLRClient()
        self._prepared = None
        self._mic_offset_ms = None
        self._goxlr_mutes = None
        self._speakers = None
        self.goxlr.connect('changed', self._on_goxlr_changed)
        self.connect('changed', lambda _mixer: self._follow_output())

    @property
    def goxlr_active(self):
        return self.goxlr.mixer is not None

    @property
    def goxlr_model(self):
        mixer = self.goxlr.mixer
        return mixer['hardware']['device_type'] if mixer else None

    def _on_goxlr_changed(self, _client):
        # A loaded profile brings its own routing, so prepare again after one
        prepared = (self.goxlr.serial, self.goxlr.mixer['profile_name']) \
            if self.goxlr_active else None
        if prepared and self._prepared != prepared:
            self._prepared = prepared
            self._prepare()
        self.emit('changed')

    def _prepare(self):
        """Sets the GoXLR up the way our mixer expects it (once per device and profile)."""
        mixer = self.goxlr.mixer
        levels = mixer['levels']
        if levels.get('submix_supported'):
            if levels.get('submix') is None:
                self.goxlr.command('SetSubMixEnabled', True)
            self.goxlr.command('SetSubMixOutputMix', 'Headphones', 'A')
            self.goxlr.command('SetSubMixOutputMix', 'BroadcastMix', 'B')
            for name in CHANNELS.values():
                self.goxlr.command('SetSubMixLinked', name, True)
        # Browser and console arrive on Sample and go to the stream through ours,
        # never to the Chat Mic that Discord records
        self.goxlr.command('SetRouter', 'Samples', 'BroadcastMix', False)
        self.goxlr.command('SetRouter', 'Samples', 'ChatMic', False)
        self._route_mic()
        self._apply_routes()

    def _mic_in_software(self):
        """RNNoise and a mic offset only work in software: the GoXLR's own
        stream mix then goes without the mic, and ours adds the processed one."""
        if self._mic_offset_ms is None:
            self._mic_offset_ms = self.offsets_ms()['mic']
        return super().filters()['rnnoise'] or self._mic_offset_ms > 0

    def _hardware(self, channel):
        return CHANNELS.get(channel) if self.goxlr_active else None

    def _submix(self):
        return self.goxlr.mixer['levels'].get('submix')

    def _routed(self, channel, output):
        return self.goxlr.mixer['router'][INPUTS[channel]][output]

    def _set_router(self, channel, output, on):
        if self._routed(channel, output) != on:
            self.goxlr.command('SetRouter', INPUTS[channel], output, on)

    # Routing matrix: the GoXLR mixes "me" and the stream of its own channels
    # in hardware, so those ways are its routing. Channels without a desk
    # fader are muted there too, which the Hub remembers as "goxlr-mutes".

    def _muted_in_routing(self):
        if self._goxlr_mutes is None:
            self._goxlr_mutes = set(self._metadata('goxlr-mutes') or [])
        return self._goxlr_mutes

    def _set_muted_in_routing(self, channel, mix, muted):
        key = f'{channel}:{mix}'
        mutes = self._muted_in_routing()
        if muted:
            mutes.add(key)
        else:
            mutes.discard(key)
        self._set_metadata('goxlr-mutes', sorted(mutes))

    def _apply_routes(self):
        """Puts the matrix, the mutes and the speakers into the GoXLR's routing."""
        routes = self.routes()
        speakers = self._on_speakers()
        for channel in GOXLR_CHANNELS:
            on_fader = self.fader_of(channel) is not None
            for mix, output in (('stream', 'BroadcastMix'), ('monitor', 'Headphones')):
                muted = not on_fader and f'{channel}:{mix}' in self._muted_in_routing()
                self._set_router(channel, output, routes[channel][mix] and not muted and
                                 not (mix == 'monitor' and speakers))
        # Listening to yourself, never on the speakers
        self._set_router('mic', 'Headphones', routes['mic']['monitor'] and not speakers)

    def _on_speakers(self):
        """The default output is another device than the GoXLR (e.g. speakers):
        the headphones go quiet and the speakers get a copy of what they'd play."""
        try:
            sink = self._pulse.get_sink_by_name(self._pulse.server_info().default_sink_name)
        except pulsectl.PulseError:
            return False
        texts = [sink.description] + [sink.proplist.get(key) for key in GOXLR_DEVICE_KEYS]
        return not any('goxlr' in (text or '').lower() for text in texts)

    def _follow_output(self):
        if not self.goxlr_active or not self.available():
            self._speakers = None
            return
        speakers = self._on_speakers()
        if speakers != self._speakers:
            self._speakers = speakers
            self._apply_routes()
        if speakers:
            # The speakers play at the volumes of the headphone mix (desk faders)
            for channel in GOXLR_CHANNELS:
                value, muted = self.fader(channel, 'monitor')
                if super().fader(channel, 'speakers') != (value, muted):
                    super().set_fader(channel, 'speakers', value)
                    super().set_fader_muted(channel, 'speakers', muted)

    def linked_routes(self, source):
        # Browser and console share the GoXLR's Sample channel
        if self.goxlr_active and source in SAMPLE_CHANNELS:
            return SAMPLE_CHANNELS
        return (source,)

    def set_route(self, source, target, on):
        super().set_route(source, target, on)
        if not self.goxlr_active:
            return
        if source == 'mic' and target == 'monitor' and on and \
                self.goxlr.mixer['levels']['volumes'].get('MicMonitor') == 0:
            self.goxlr.command('SetVolume', 'MicMonitor', MIC_MONITOR_VOLUME)
        self._route_mic()
        self._apply_routes()

    def reset_routes(self):
        super().reset_routes()
        if self.goxlr_active:
            self._route_mic()
            self._apply_routes()

    def _button_mutes(self, name):
        """(stream, headphones) muted by the mute button of this channel's desk fader."""
        for status in self.goxlr.mixer['fader_status'].values():
            if status['channel'] != name or status['mute_state'] == 'Unmuted':
                continue
            if status['mute_state'] == 'MutedToAll':
                return True, True
            return MUTED_MIXES.get(status['mute_type'], (False, False))
        return False, False

    def _set_button_mutes(self, letter, stream, monitor):
        if stream or monitor:
            self.goxlr.command('SetFaderMuteFunction', letter, MUTE_FUNCTIONS[(stream, monitor)])
            self.goxlr.command('SetFaderMuteState', letter, 'MutedToX')
        else:
            self.goxlr.command('SetFaderMuteState', letter, 'Unmuted')
            # A press on the desk mutes everything again
            self.goxlr.command('SetFaderMuteFunction', letter, 'All')

    # Faders

    def fader(self, channel, mix):
        name = self._hardware(channel)
        if name is None:
            return super().fader(channel, mix)
        volume = self.goxlr.mixer['levels']['volumes'][name]
        submix = self._submix()
        if mix == 'stream' and submix is not None:
            volume = submix['inputs'][name]['volume']
        stream, monitor = self._button_mutes(name)
        muted = (stream if mix == 'stream' else monitor) or (
            self.fader_of(channel) is None and f'{channel}:{mix}' in self._muted_in_routing())
        return _from_goxlr(volume), muted

    def set_fader(self, channel, mix, value):
        name = self._hardware(channel)
        if name is None:
            super().set_fader(channel, mix, value)
        elif mix == 'stream' and self._submix() is not None:
            self.goxlr.command('SetSubMixVolume', name, _to_goxlr(value))
        else:
            self.goxlr.command('SetVolume', name, _to_goxlr(value))

    def set_fader_muted(self, channel, mix, muted):
        if self._hardware(channel) is None:
            super().set_fader_muted(channel, mix, muted)
            return
        letter = self.fader_of(channel)
        if letter is None:
            self._set_muted_in_routing(channel, mix, muted)
            self._apply_routes()
            return
        mutes = {other: self.fader(channel, other)[1] for other in ('stream', 'monitor')}
        mutes[mix] = muted
        # The button takes over, so a mute left in the routing must go
        self._apply_routes()
        self._set_button_mutes(letter, mutes['stream'], mutes['monitor'])

    def mic(self):
        if not self.goxlr_active:
            return super().mic()
        volume = self.goxlr.mixer['levels']['volumes']['Mic']
        muted = not self._routed('mic', 'ChatMic') or any(self._button_mutes('Mic'))
        return _from_goxlr(volume), muted

    def set_mic(self, value):
        if not self.goxlr_active:
            super().set_mic(value)
        else:
            self.goxlr.command('SetVolume', 'Mic', _to_goxlr(value))

    def set_mic_muted(self, muted):
        if not self.goxlr_active:
            super().set_mic_muted(muted)
            return
        letter = self.fader_of('mic')
        if letter is not None:
            self.goxlr.command('SetRouter', 'Microphone', 'ChatMic', True)
            self.goxlr.command('SetRouter', 'Microphone', 'BroadcastMix', self._mic_to_stream())
            self._set_button_mutes(letter, muted, muted)
            return
        self.goxlr.command('SetRouter', 'Microphone', 'ChatMic', not muted)
        self.goxlr.command('SetRouter', 'Microphone', 'BroadcastMix',
                           not muted and self._mic_to_stream())

    # Mic setup: type (Condenser = 48 V phantom power) and gain per type

    def mic_type(self):
        if not self.goxlr_active:
            return None
        return self.goxlr.mixer['mic_status']['mic_type']

    def set_mic_type(self, mic_type):
        self.goxlr.command('SetMicrophoneType', mic_type)

    def mic_gain_db(self):
        mic = self.goxlr.mixer['mic_status']
        return mic['mic_gains'][mic['mic_type']]

    def set_mic_gain_db(self, gain_db):
        self.goxlr.command('SetMicrophoneGain', self.mic_type(), round(gain_db))

    # Profiles: the GoXLR Utility keeps the device settings and the mic
    # settings (type, gain, gate, compressor, EQ) in two profile files

    def profiles(self, mic=False):
        files = (self.goxlr.status or {}).get('files') or {}
        return sorted(files.get('mic_profiles' if mic else 'profiles') or [], key=str.lower)

    def profile(self, mic=False):
        return self.goxlr.mixer['mic_profile_name' if mic else 'profile_name']

    def load_profile(self, name, mic=False):
        self.goxlr.command('LoadMicProfile' if mic else 'LoadProfile', name, True)

    def save_profiles(self):
        self.goxlr.command('SaveProfile')
        self.goxlr.command('SaveMicProfile')

    def import_profile(self, path):
        """Copies a profile file (from the GoXLR Utility or the Windows app)
        into the profile folder and loads it. False if it's no profile."""
        path = Path(path)
        mic = path.suffix == MIC_PROFILE_SUFFIX
        if not mic and path.suffix != PROFILE_SUFFIX:
            return False
        paths = self.goxlr.status['paths']
        folder = Path(paths['mic_profile_directory' if mic else 'profile_directory'])
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, folder / path.name)
        self.load_profile(path.stem, mic)
        return True

    # Filters

    def filters(self):
        filters = super().filters()
        if self.goxlr_active:
            mic = self.goxlr.mixer['mic_status']
            filters['gate'] = mic['noise_gate']['enabled']
            filters['compressor'] = mic['compressor']['ratio'] != COMPRESSOR_OFF
            eq, keys = self._eq()
            filters['eq'] = [eq['gain'][key] for key in keys]
        return filters

    def set_filter(self, name, active):
        if not self.goxlr_active or name == 'rnnoise':
            super().set_filter(name, active)
        if not self.goxlr_active:
            return
        if name == 'rnnoise':
            self._route_mic()
        elif name == 'gate':
            self.goxlr.command('SetGateActive', active)
        elif name == 'compressor':
            self.goxlr.command('SetCompressorRatio',
                               COMPRESSOR_ON if active else COMPRESSOR_OFF)

    # Offsets

    def set_offset_ms(self, target, ms):
        super().set_offset_ms(target, ms)
        if target == 'mic':
            self._mic_offset_ms = ms
            if self.goxlr_active:
                self._route_mic()

    def _mic_to_stream(self):
        """The GoXLR's own stream mix carries the mic (else ours adds it, or nobody)."""
        return self.routes()['mic']['stream'] and not self._mic_in_software()

    def _route_mic(self):
        muted = self.mic()[1]
        self.goxlr.command('SetRouter', 'Microphone', 'BroadcastMix',
                           not muted and self._mic_to_stream())

    def _eq(self):
        mic = self.goxlr.mixer['mic_status']
        if self.goxlr_model == 'Mini':
            return mic['equaliser_mini'], [f'Equalizer{band}' for band in MINI_EQ]
        return mic['equaliser'], [f'Equalizer{band}' for band in FULL_EQ]

    def eq_bands(self):
        if not self.goxlr_active:
            return super().eq_bands()
        eq, keys = self._eq()
        return [eq['frequency'][key] for key in keys]

    def eq_range_db(self):
        return EQ_RANGE_DB

    def set_eq_gain(self, band, gain_db):
        if not self.goxlr_active:
            super().set_eq_gain(band, gain_db)
            return
        _eq, keys = self._eq()
        command = 'SetEqMiniGain' if self.goxlr_model == 'Mini' else 'SetEqGain'
        self.goxlr.command(command, keys[band], round(gain_db))

    # Hardware faders

    def fader_of(self, channel):
        """Letter of the desk fader this channel sits on ("A"-"D"), or None."""
        name = self._hardware(channel)
        if name is None:
            return None
        for letter in FADERS:
            if self.goxlr.mixer['fader_status'][letter]['channel'] == name:
                return letter
        return None

    def fader_choices(self):
        return FADER_CHOICES

    def put_on_fader(self, letter, channel):
        self.goxlr.command('SetFader', letter, CHANNELS[channel])
