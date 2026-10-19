#!/usr/bin/env python3
"""Generates the PipeWire config of the SoftglowOS mixer.

The graph, per channel (game, chat, music, system, browser, console):

  apps ──> sink "softglowos.<ch>" ──[stream fader]──> source "softglowos.<ch>.stream.out"
                               │                         │  (single track for OBS)
                               │                         └──> sink "softglowos.stream-mix"
                               └──[headphone fader]──> your headphones (default output)

With a GoXLR, the GoXLR mixes in hardware instead: game, chat, music and
system go 1:1 into the GoXLR channel of the same name (its faders are the
volume), browser and console go into its Sample channel, which the Hub takes
out of the GoXLR's own stream mix, and the GoXLR's "Stream Mix 1" is fed into
our stream mix. So OBS always records "SoftglowOS Stream-Mix". The WirePlumber
script switches between both ways when a GoXLR comes or goes.

The microphone runs through a filter chain (RNNoise, gate, 10-band EQ,
compressor) into the source "softglowos.mic", which is also the default input,
so Discord and OBS get the same filtered mic. The capture card runs through a
delay filter (the "offset", 0 ms by default) into the console channel.

Every other channel has an offset too: its stream and headphone faders (and
its way into the GoXLR) are delay filters instead of plain loopbacks, all set
to the same delay by the Hub. The mic's offset sits only on its way into the
stream mix, so Discord gets it undelayed. At 0 ms a delay filter passes the
sound straight through.

Fader volumes live on the capture side of each loopback, which is a stream, so
WirePlumber remembers them. The WirePlumber script picks the real devices and
links or unlinks the loopbacks for the current mode; node.linger keeps an
unlinked loopback waiting instead of being torn down.

Run from the repo root:
  python3 tools/make-audio-config.py
"""
from pathlib import Path

OUT = Path("files/system/usr/share/pipewire/pipewire.conf.d/60-softglowos-mixer.conf")

CHANNELS = [
    ("game", "Game"),
    ("chat", "Chat"),
    ("music", "Music"),
    ("system", "System"),
    ("browser", "Browser"),
    ("console", "Console"),
]

# Channels the GoXLR mixes itself (it has a channel of the same name).
GOXLR_CHANNELS = ["game", "chat", "music", "system"]

# LSP "Bypass" = 1 switches a filter off. Defaults as in the Hub mockup:
# RNNoise and compressor on, gate off, EQ flat.

# Same bands as the full-size GoXLR, so the software EQ feels the same.
EQ_BANDS = [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
EQ_Q = 1.41  # about one octave per band

# Longest offset the Hub allows (OFFSET_MAX_MS in apps/hub/src/strips.py)
MAX_OFFSET_S = 2.0

LSP = "lsp-plugins-ladspa"
LSP_GATE = "http://lsp-plug.in/plugins/ladspa/gate_mono"
LSP_COMPRESSOR = "http://lsp-plug.in/plugins/ladspa/compressor_mono"


def null_sink(name, description):
    return f"""  {{ factory = adapter
    args = {{
      factory.name     = support.null-audio-sink
      node.name        = "{name}"
      node.description = "{description}"
      media.class      = Audio/Sink
      audio.position   = [ FL FR ]
      monitor.channel-volumes = true
      priority.session = 0
      priority.driver  = 0
      object.linger    = true
    }}
  }}"""


def loopback(name, description, capture, playback):
    def props(items):
        return "\n".join(f"        {k} = {v}" for k, v in items.items())

    return f"""  {{ name = libpipewire-module-loopback
    args = {{
      node.description = "{description}"
      audio.position   = [ FL FR ]
      capture.props = {{
        node.name  = "{name}.in"
        media.name = "{name}.in"
        node.linger = true
{props(capture)}
      }}
      playback.props = {{
        node.name  = "{name}.out"
        media.name = "{name}.out"
        node.linger = true
{props(playback)}
      }}
    }}
  }}"""


def delayed_loopback(name, description, capture, playback):
    """Like loopback(), with the offset's delay filter in between. Same node
    names, so faders and the WirePlumber script treat both the same."""
    def props(items):
        return "\n".join(f"        {k} = {v}" for k, v in items.items())

    return f"""  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "{description}"
      media.name       = "{description}"
      filter.graph = {{
        nodes = [
          {{ type = builtin name = offset label = delay
            config = {{ "max-delay" = {MAX_OFFSET_S} }}
            control = {{ "Delay (s)" = 0.0 }} }}
        ]
      }}
      audio.rate     = 48000
      audio.channels = 2
      audio.position = [ FL FR ]
      capture.props = {{
        node.name  = "{name}.in"
        media.name = "{name}.in"
        node.linger = true
{props(capture)}
      }}
      playback.props = {{
        node.name  = "{name}.out"
        media.name = "{name}.out"
        node.linger = true
{props(playback)}
      }}
    }}
  }}"""


def channel_modules(ch, label):
    sink = f'"softglowos.{ch}"'
    # The console's offset sits right after the capture card instead
    fader = loopback if ch == "console" else delayed_loopback
    return [
        # Stream fader: channel -> its single track (a source OBS can record)
        fader(f"softglowos.{ch}.stream", f"SoftglowOS {label} (Stream)",
                 {"target.object": sink, "stream.capture.sink": "true"},
                 {"media.class": "Audio/Source",
                  "node.description": f'"SoftglowOS {label} (Stream)"',
                  "priority.session": "0"}),
        # Track -> stream mix, always at full volume
        loopback(f"softglowos.{ch}.mix", f"SoftglowOS {label} to Stream-Mix",
                 {"target.object": f'"softglowos.{ch}.stream.out"'},
                 {"target.object": '"softglowos.stream-mix"'}),
        # Headphone fader: channel -> your headphones (picked by the script)
        fader(f"softglowos.{ch}.monitor", f"SoftglowOS {label} (Me)",
                 {"target.object": sink, "stream.capture.sink": "true"},
                 {}),
    ]


def mic_chain():
    eq_nodes = "\n".join(
        f'          {{ type = builtin name = eq{i} label = bq_peaking '
        f'control = {{ "Freq" = {freq} "Q" = {EQ_Q} "Gain" = 0.0 }} }}'
        for i, freq in enumerate(EQ_BANDS, 1))
    eq_links = "\n".join(
        f'          {{ output = "eq{i}:Out" input = "eq{i + 1}:In" }}'
        for i in range(1, len(EQ_BANDS)))
    return f"""  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "SoftglowOS Microphone"
      media.name       = "SoftglowOS Microphone"
      filter.graph = {{
        nodes = [
          # RNNoise on/off: the mixer picks the denoised (Gain 1) or dry (Gain 2) signal
          {{ type = builtin name = split label = copy }}
          {{ type = ladspa name = rnnoise plugin = librnnoise_ladspa label = noise_suppressor_mono
            control = {{ "VAD Threshold (%)" = 0.0 }} }}
          {{ type = builtin name = rnnoise_mix label = mixer
            control = {{ "Gain 1" = 1.0 "Gain 2" = 0.0 }} }}
          {{ type = ladspa name = gate plugin = {LSP} label = "{LSP_GATE}"
            control = {{
              "Bypass" = 1.0
              "Curve threshold (G)" = 0.0316
              "Reduction (G)" = 0.01
              "Attack (ms)" = 5.0
              "Hold time (ms)" = 100.0
              "Release (ms)" = 200.0
            }} }}
{eq_nodes}
          {{ type = ladspa name = compressor plugin = {LSP} label = "{LSP_COMPRESSOR}"
            control = {{
              "Bypass" = 0.0
              "Attack threshold (G)" = 0.178
              "Ratio" = 3.0
              "Attack time (ms)" = 10.0
              "Release time (ms)" = 100.0
            }} }}
        ]
        links = [
          {{ output = "split:Out" input = "rnnoise:Input" }}
          {{ output = "rnnoise:Output" input = "rnnoise_mix:In 1" }}
          {{ output = "split:Out" input = "rnnoise_mix:In 2" }}
          {{ output = "rnnoise_mix:Out" input = "gate:Input" }}
          {{ output = "gate:Output" input = "eq1:In" }}
{eq_links}
          {{ output = "eq{len(EQ_BANDS)}:Out" input = "compressor:Input" }}
        ]
        inputs  = [ "split:In" ]
        outputs = [ "compressor:Output" ]
      }}
      audio.rate     = 48000
      audio.channels = 1
      audio.position = [ MONO ]
      capture.props = {{
        node.name  = "softglowos.mic.in"
        media.name = "softglowos.mic.in"
        node.linger = true
      }}
      playback.props = {{
        node.name        = "softglowos.mic"
        media.name       = "softglowos.mic"
        node.description = "SoftglowOS Microphone"
        media.class      = Audio/Source
        priority.session = 2500
      }}
    }}
  }}"""


def console_delay():
    return """  { name = libpipewire-module-filter-chain
    args = {
      node.description = "SoftglowOS Console Offset"
      media.name       = "SoftglowOS Console Offset"
      filter.graph = {
        nodes = [
          { type = builtin name = offset label = delay
            config = { "max-delay" = %s }
            control = { "Delay (s)" = 0.0 } }
        ]
      }
      audio.rate     = 48000
      audio.channels = 2
      audio.position = [ FL FR ]
      capture.props = {
        node.name  = "softglowos.console-offset.in"
        media.name = "softglowos.console-offset.in"
        node.linger = true
      }
      playback.props = {
        node.name  = "softglowos.console-offset.out"
        media.name = "softglowos.console-offset.out"
        node.linger = true
        target.object = "softglowos.console"
      }
    }
  }""" % MAX_OFFSET_S


def main():
    sinks = [null_sink(f"softglowos.{ch}", f"SoftglowOS {label}") for ch, label in CHANNELS]
    sinks.append(null_sink("softglowos.stream-mix", "SoftglowOS Stream-Mix"))

    modules = []
    for ch, label in CHANNELS:
        modules += channel_modules(ch, label)
    modules.append(mic_chain())
    modules.append(delayed_loopback("softglowos.mic.mix", "SoftglowOS Microphone to Stream-Mix",
                            {"target.object": '"softglowos.mic"'},
                            {"target.object": '"softglowos.stream-mix"'}))
    modules.append(console_delay())
    for ch, label in CHANNELS:
        if ch in GOXLR_CHANNELS:
            # Only linked with a GoXLR: channel -> GoXLR channel at full volume
            modules.append(delayed_loopback(f"softglowos.{ch}.goxlr", f"SoftglowOS {label} to GoXLR",
                                    {"target.object": f'"softglowos.{ch}"',
                                     "stream.capture.sink": "true"},
                                    {}))
    # Only linked with a GoXLR: its hardware stream mix -> our stream mix
    modules.append(loopback("softglowos.goxlr-stream", "SoftglowOS GoXLR Stream Mix",
                            {}, {"target.object": '"softglowos.stream-mix"'}))

    text = (
        "# SoftglowOS mixer graph. Generated by tools/make-audio-config.py, don't edit.\n\n"
        "context.objects = [\n" + "\n".join(sinks) + "\n]\n\n"
        "context.modules = [\n" + "\n".join(modules) + "\n]\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
