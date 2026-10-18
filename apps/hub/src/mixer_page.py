from gi.repository import Adw, GLib, Gtk

from .strips import ChannelStrip, MicStrip

# Placeholder values until the mixer talks to PipeWire. Per channel:
# id, name, apps, stream volume, headphone volume, level in % (fake meter).
CHANNELS = (
    ('game', _('Game'), ['Steam'], 80, 70, 64),
    ('chat', _('Chat'), ['Discord'], 65, 85, 46),
    ('music', _('Music'), ['Spotify'], 30, 55, 38),
    ('system', _('System'), [_('Notifications')], 0, 45, 0),
    ('browser', _('Browser'), ['Chrome'], 50, 60, 22),
    ('console', _('Console'), ['Elgato 4K X'], 75, 70, 58),
)


@Gtk.Template(resource_path='/com/softglowos/Hub/mixer-page.ui')
class MixerPage(Adw.Bin):
    __gtype_name__ = 'MixerPage'

    listening_label = Gtk.Template.Child()
    stream_label = Gtk.Template.Child()
    strips = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.listening_label.set_markup(_('Listening on <b>{device}</b>').format(
            device=GLib.markup_escape_text('GoXLR Headphones')))
        self.stream_label.set_markup(_('Stream goes to <b>{target}</b>').format(
            target=GLib.markup_escape_text('OBS')))

        self.strips.append(MicStrip(device='GoXLR Mic', value=72, level=70))
        for channel_id, name, apps, stream, headphones, level in CHANNELS:
            self.strips.append(ChannelStrip(
                name, apps, stream, headphones, level,
                stream_muted=channel_id == 'system',
                offset_ms=120 if channel_id == 'console' else None,
            ))
