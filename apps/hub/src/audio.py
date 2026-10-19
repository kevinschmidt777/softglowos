"""Talks to the SoftglowOS mixer graph in PipeWire.

The graph itself lives in PipeWire and WirePlumber (see
tools/make-audio-config.py and the WirePlumber script audio.lua), so audio
keeps working while the Hub is closed. The Hub only reads and changes it:

- fader volumes and mutes sit on loopback streams (PulseAudio API)
- filter settings (RNNoise, gate, compressor, EQ) and offsets are controls
  of filter-chain nodes (pw-cli)
- level meters record the channel sinks with GStreamer
"""
import json
import math
import subprocess
import threading
import time

import gi

gi.require_version('Gst', '1.0')

import pulsectl
from gi.repository import GLib, GObject, Gst

PREFIX = 'softglowos.'
CHANNELS = ('game', 'chat', 'music', 'system', 'browser', 'console')
MIXES = ('stream', 'monitor')  # stream fader, headphone ("Me") fader

MIC_FILTER = PREFIX + 'mic.in'
CONSOLE_FILTER = PREFIX + 'console-offset.in'
GOXLR_CHANNELS = ('game', 'chat', 'music', 'system')

# Delay filters behind each offset. A channel's offset delays its stream and
# headphone faders (and the way into the GoXLR), the console's sits right
# after the capture card, the mic's only on its way into the stream mix.
OFFSET_NODES = {
    channel: tuple(f'{PREFIX}{channel}.{path}.in' for path in
                   (('stream', 'monitor', 'goxlr') if channel in GOXLR_CHANNELS
                    else ('stream', 'monitor')))
    for channel in CHANNELS if channel != 'console'
}
OFFSET_NODES['console'] = (CONSOLE_FILTER,)
OFFSET_NODES['mic'] = (PREFIX + 'mic.mix.in',)
OFFSET_CONTROL = 'offset:Delay (s)'

# Same bands as the full-size GoXLR, see tools/make-audio-config.py.
EQ_BANDS = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
EQ_RANGE_DB = 9

CAPTURE_CARD_WORDS = ('elgato', 'game capture', 'cam link', 'avermedia',
                      'live gamer', 'usb3.0 capture', 'hdmi capture')

METER_INTERVAL_NS = 50 * Gst.MSECOND
METER_FLOOR_DB = -60.0
RECONNECT_DELAY_S = 1


def is_capture_card(description):
    text = (description or '').lower()
    return any(word in text for word in CAPTURE_CARD_WORDS)


class Device:
    def __init__(self, name, description):
        self.name = name
        self.description = description


class App:
    def __init__(self, index, name):
        self.index = index
        self.name = name


class PipeWireMixer(GObject.Object):
    """The mixer without a GoXLR. Emits "changed" when anything outside the
    Hub changes the graph, and "levels" with fresh meter values."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'levels': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self):
        super().__init__()
        self._pulse = pulsectl.Pulse('softglowos-hub')
        self._connected = True
        self._node_ids = {}
        self._refresh_pending = False
        self._meters = []
        self._levels = {}
        self._filters = None

        Gst.init(None)
        threading.Thread(target=self._listen, daemon=True).start()

    def available(self):
        """False when the SoftglowOS mixer graph isn't there (e.g. PipeWire is down)."""
        if not self._connected:
            return False
        try:
            return self._loopback('system', 'stream') is not None
        except pulsectl.PulseError:
            return False

    # Faders

    def _loopback(self, channel, mix):
        name = f'{PREFIX}{channel}.{mix}.in'
        for stream in self._pulse.source_output_list():
            if stream.proplist.get('node.name') == name:
                return stream
        return None

    def fader(self, channel, mix):
        """Volume (0-100) and mute of a stream or headphone fader."""
        stream = self._loopback(channel, mix)
        if stream is None:
            return 0, False
        return round(stream.volume.value_flat * 100), bool(stream.mute)

    def set_fader(self, channel, mix, value):
        stream = self._loopback(channel, mix)
        if stream is not None:
            self._pulse.volume_set_all_chans(stream, value / 100)

    def set_fader_muted(self, channel, mix, muted):
        stream = self._loopback(channel, mix)
        if stream is not None:
            self._pulse.source_output_mute(stream.index, muted)

    # Microphone level and mute (before the filters, so Discord gets it too)

    def _mic_stream(self):
        for stream in self._pulse.source_output_list():
            if stream.proplist.get('node.name') == MIC_FILTER:
                return stream
        return None

    def mic(self):
        stream = self._mic_stream()
        if stream is None:
            return 0, False
        return round(stream.volume.value_flat * 100), bool(stream.mute)

    def set_mic(self, value):
        stream = self._mic_stream()
        if stream is not None:
            self._pulse.volume_set_all_chans(stream, value / 100)

    def set_mic_muted(self, muted):
        stream = self._mic_stream()
        if stream is not None:
            self._pulse.source_output_mute(stream.index, muted)

    # Filters

    def _node_id(self, name):
        if name not in self._node_ids:
            for obj in self._pw_dump():
                props = obj.get('info', {}).get('props', {})
                if obj.get('type', '').endswith(':Node') and props.get('node.name') == name:
                    self._node_ids[name] = obj['id']
        return self._node_ids.get(name)

    @staticmethod
    def _pw_dump():
        try:
            return json.loads(subprocess.run(['pw-dump'], capture_output=True,
                                             text=True, timeout=5).stdout or '[]')
        except (subprocess.SubprocessError, json.JSONDecodeError):
            return []

    def _controls(self, name):
        """Current filter controls of a filter-chain node, e.g. {"eq3:Gain": 4.5}."""
        return self._all_controls().get(name, {})

    def _all_controls(self):
        """Filter controls of every node at once (one pw-dump), by node name."""
        nodes = {}
        for obj in self._pw_dump():
            info = obj.get('info', {})
            controls = nodes.setdefault(info.get('props', {}).get('node.name'), {})
            for props in info.get('params', {}).get('Props', []):
                params = props.get('params', [])
                for key, value in zip(params[::2], params[1::2]):
                    controls[key] = value
        return nodes

    def _set_controls(self, name, controls):
        node_id = self._node_id(name)
        if node_id is None:
            return
        params = ' '.join(f'"{key}" {float(value)}' for key, value in controls.items())
        subprocess.run(['pw-cli', 'set-param', str(node_id), 'Props',
                        f'{{ params = [ {params} ] }}'],
                       capture_output=True, timeout=5)

    def filters(self):
        """RNNoise, gate and compressor on/off plus the EQ gains in dB.
        Read from PipeWire once; afterwards only the Hub changes them."""
        if self._filters is None:
            controls = self._controls(MIC_FILTER)
            self._filters = {
                'rnnoise': controls.get('rnnoise_mix:Gain 1', 1.0) > 0.5,
                'gate': not controls.get('gate:Bypass', True),
                'compressor': not controls.get('compressor:Bypass', False),
                'eq': [controls.get(f'eq{i}:Gain', 0.0) for i in range(1, len(EQ_BANDS) + 1)],
            }
        return {**self._filters, 'eq': list(self._filters['eq'])}

    def set_filter(self, name, active):
        self.filters()
        self._filters[name] = active
        if name == 'rnnoise':
            self._set_controls(MIC_FILTER, {'rnnoise_mix:Gain 1': 1.0 if active else 0.0,
                                            'rnnoise_mix:Gain 2': 0.0 if active else 1.0})
        else:
            self._set_controls(MIC_FILTER, {f'{name}:Bypass': 0.0 if active else 1.0})

    def eq_bands(self):
        return EQ_BANDS

    def eq_range_db(self):
        return EQ_RANGE_DB

    def set_eq_gain(self, band, gain_db):
        self.filters()
        self._filters['eq'][band] = gain_db
        self._set_controls(MIC_FILTER, {f'eq{band + 1}:Gain': gain_db})

    def offsets_ms(self):
        """Offset of every channel and the mic in ms, e.g. {"game": 0, "mic": 40}."""
        nodes = self._all_controls()
        return {target: round(nodes.get(names[0], {}).get(OFFSET_CONTROL, 0.0) * 1000)
                for target, names in OFFSET_NODES.items()}

    def set_offset_ms(self, target, ms):
        for name in OFFSET_NODES[target]:
            self._set_controls(name, {OFFSET_CONTROL: ms / 1000})

    # Devices

    def outputs(self):
        return [Device(s.name, s.description) for s in self._pulse.sink_list()
                if not s.name.startswith(PREFIX)]

    def current_output(self):
        name = self._pulse.server_info().default_sink_name
        return next((d for d in self.outputs() if d.name == name), None)

    def set_output(self, device):
        self._pulse.default_set(self._pulse.get_sink_by_name(device.name))

    def _real_sources(self):
        return [s for s in self._pulse.source_list()
                if not s.name.startswith(PREFIX) and not s.name.endswith('.monitor')]

    def microphones(self):
        return [Device(s.name, s.description) for s in self._real_sources()
                if not is_capture_card(s.description)]

    def capture_cards(self):
        return [Device(s.name, s.description) for s in self._real_sources()]

    def _source_of(self, stream_name):
        for stream in self._pulse.source_output_list():
            if stream.proplist.get('node.name') == stream_name:
                for source in self._pulse.source_list():
                    if source.index == stream.source:
                        return Device(source.name, source.description)
        return None

    def current_microphone(self):
        return self._source_of(MIC_FILTER)

    def current_capture_card(self):
        return self._source_of(CONSOLE_FILTER)

    def _move(self, stream_name, device):
        for stream in self._pulse.source_output_list():
            if stream.proplist.get('node.name') == stream_name:
                source = self._pulse.get_source_by_name(device.name)
                self._pulse.source_output_move(stream.index, source.index)

    def set_microphone(self, device):
        self._move(MIC_FILTER, device)

    def set_capture_card(self, device):
        self._move(CONSOLE_FILTER, device)

    # Apps in the channels

    def apps(self):
        """{channel: [App, ...]} for every app currently playing into a channel."""
        sinks = {s.index: s.name[len(PREFIX):] for s in self._pulse.sink_list()
                 if s.name.startswith(PREFIX)}
        result = {channel: [] for channel in CHANNELS}
        for stream in self._pulse.sink_input_list():
            channel = sinks.get(stream.sink)
            name = stream.proplist.get('application.name')
            if channel in result and name and not stream.proplist.get(
                    'node.name', '').startswith(PREFIX):
                result[channel].append(App(stream.index, name))
        return result

    def move_app(self, app, channel):
        """Moves an app into another channel. WirePlumber remembers it per app."""
        sink = self._pulse.get_sink_by_name(PREFIX + channel)
        self._pulse.sink_input_move(app.index, sink.index)

    # Level meters

    def start_meters(self):
        if self._meters:
            return
        targets = [(channel, PREFIX + channel, True) for channel in CHANNELS]
        targets.append(('mic', PREFIX + 'mic', False))
        for key, target, from_sink in targets:
            # softglowos.* names keep the meters out of the mic indicator
            props = f'props,node.name={PREFIX}hub.meter.{key},media.name={PREFIX}hub.meter.{key}'
            if from_sink:
                props += ',stream.capture.sink=true'
            pipeline = Gst.parse_launch(
                f'pipewiresrc target-object={target} stream-properties="{props}" '
                f'! audioconvert ! level interval={METER_INTERVAL_NS} post-messages=true '
                f'! fakesink sync=false')
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message::element', self._on_level, key)
            pipeline.set_state(Gst.State.PLAYING)
            self._meters.append(pipeline)

    def stop_meters(self):
        for pipeline in self._meters:
            pipeline.set_state(Gst.State.NULL)
        self._meters = []

    def _on_level(self, _bus, message, key):
        structure = message.get_structure()
        if structure is None or structure.get_name() != 'level':
            return
        peak = max(structure.get_value('peak'))
        level = 0.0 if math.isinf(peak) else max(0.0, 1 - peak / METER_FLOOR_DB)
        self._levels[key] = min(level, 1.0)
        self.emit('levels', dict(self._levels))

    # Changes made elsewhere (GNOME settings, other apps, WirePlumber)

    def _listen(self):
        while True:
            try:
                with pulsectl.Pulse('softglowos-hub-events') as events:
                    events.event_mask_set('sink', 'source', 'sink_input', 'source_output', 'server')
                    events.event_callback_set(self._on_event)
                    GLib.idle_add(self._reconnect)
                    while True:
                        events.event_listen()
            except (pulsectl.PulseError, pulsectl.PulseDisconnected):
                # PipeWire restarted (e.g. after an update) or isn't up yet
                GLib.idle_add(self._disconnected)
                time.sleep(RECONNECT_DELAY_S)

    # Both run on the GTK thread, like every other use of self._pulse

    def _disconnected(self):
        """Shows the mixer as missing instead of touching the dead connection."""
        if self._connected:
            self._connected = False
            self._emit_changed()
        return GLib.SOURCE_REMOVE

    def _reconnect(self):
        """Swaps in a fresh connection once PipeWire is back."""
        if self._connected:
            return GLib.SOURCE_REMOVE  # the Hub just started
        self._pulse.close()
        try:
            self._pulse = pulsectl.Pulse('softglowos-hub')
        except pulsectl.PulseError:
            GLib.timeout_add_seconds(RECONNECT_DELAY_S, self._reconnect)
            return GLib.SOURCE_REMOVE
        self._connected = True
        if self._meters:
            self.stop_meters()
            self.start_meters()
        self._emit_changed()
        return GLib.SOURCE_REMOVE

    def _on_event(self, _event):
        if not self._refresh_pending:
            self._refresh_pending = True
            GLib.timeout_add(100, self._emit_changed)

    def _emit_changed(self):
        self._refresh_pending = False
        self._node_ids.clear()
        self.emit('changed')
        return GLib.SOURCE_REMOVE
