from gi.repository import Gtk

FADER_HEIGHT = 184
OFFSET_STEP_MS = 10


class Fader(Gtk.Box):
    """A vertical fader with level meter, value, optional mute button and caption."""

    def __init__(self, value, level, accessible_name, caption=None,
                 mute_tooltip=None, muted=False, unit=''):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         halign=Gtk.Align.CENTER)
        self._level = level
        self._unit = unit

        controls = Gtk.Box(spacing=3, halign=Gtk.Align.CENTER)
        self.meter = Gtk.LevelBar(orientation=Gtk.Orientation.VERTICAL, inverted=True,
                                  min_value=0, max_value=100, height_request=FADER_HEIGHT)
        self.meter.add_css_class('meter')
        for offset in ('low', 'high', 'full'):
            self.meter.remove_offset_value(offset)
        controls.append(self.meter)

        self.scale = Gtk.Scale(
            orientation=Gtk.Orientation.VERTICAL, inverted=True, draw_value=False,
            height_request=FADER_HEIGHT,
            adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1,
                                      page_increment=10, value=value),
        )
        self.scale.add_css_class('fader')
        self.scale.update_property([Gtk.AccessibleProperty.LABEL], [accessible_name])
        self.scale.connect('value-changed', lambda _scale: self._update())
        controls.append(self.scale)
        self.append(controls)

        self.value_label = Gtk.Label()
        self.value_label.add_css_class('monospace')
        self.value_label.add_css_class('dim-label')
        self.append(self.value_label)

        self.mute_button = None
        if mute_tooltip:
            self.mute_button = Gtk.ToggleButton(tooltip_text=mute_tooltip,
                                                halign=Gtk.Align.CENTER)
            self.mute_button.add_css_class('circular')
            self.mute_button.add_css_class('mute-button')
            self.mute_button.connect('toggled', lambda button: self.set_muted(button.get_active()))
            self.append(self.mute_button)

        if caption:
            caption_label = Gtk.Label(label=caption)
            caption_label.add_css_class('caption')
            caption_label.add_css_class('dim-label')
            self.append(caption_label)

        self._muted = False
        self.set_muted(muted)

    def set_muted(self, muted):
        self._muted = muted
        if muted:
            self.add_css_class('muted')
        else:
            self.remove_css_class('muted')
        if self.mute_button:
            self.mute_button.set_active(muted)
            self.mute_button.set_icon_name(
                'audio-volume-muted-symbolic' if muted else 'audio-volume-high-symbolic')
        self._update()

    def _update(self):
        value = round(self.scale.get_value())
        self.value_label.set_label(f'{value}{self._unit}')
        self.meter.set_value(0 if self._muted else self._level * value / 100)


def _strip_box(**kwargs):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, **kwargs)
    box.add_css_class('card')
    box.add_css_class('mixer-strip')
    return box


class MicStrip(Gtk.Box):
    """The microphone input: fader, filters and a mute button."""

    def __init__(self, device, value, level):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        strip = _strip_box(spacing=14, width_request=208, vexpand=True)
        self.append(strip)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=_('Microphone'), xalign=0)
        title.add_css_class('heading')
        heading.append(title)
        subtitle = Gtk.Label(label=device, xalign=0)
        subtitle.add_css_class('caption')
        subtitle.add_css_class('dim-label')
        heading.append(subtitle)
        strip.append(heading)

        self.fader = Fader(value, level, _('Microphone level'), unit=' %')
        strip.append(self.fader)

        filters = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        filters.add_css_class('strip-section')
        for label, active in ((_('Noise suppression'), True),
                              (_('Compressor'), True),
                              (_('Noise gate'), False)):
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            switch = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
            switch.update_property([Gtk.AccessibleProperty.LABEL], [label])
            row.append(switch)
            filters.append(row)
        strip.append(filters)

        self.mute_button = Gtk.ToggleButton(label=_('Mute'), valign=Gtk.Align.END,
                                            vexpand=True)
        self.mute_button.add_css_class('mute-button')
        self.mute_button.connect('toggled', self._on_mute_toggled)
        strip.append(self.mute_button)

    def _on_mute_toggled(self, button):
        muted = button.get_active()
        button.set_label(_('Muted – unmute') if muted else _('Mute'))
        self.fader.set_muted(muted)


class ChannelStrip(Gtk.Box):
    """One mixer channel with a stream fader and a headphone fader."""

    def __init__(self, name, apps, stream, headphones, level,
                 stream_muted=False, offset_ms=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        strip = _strip_box(spacing=12, width_request=112, vexpand=True)
        self.append(strip)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          halign=Gtk.Align.CENTER, height_request=48)
        title = Gtk.Label(label=name)
        title.add_css_class('heading')
        heading.append(title)
        for app in apps:
            chip = Gtk.Label(label=app, halign=Gtk.Align.CENTER)
            chip.add_css_class('app-chip')
            heading.append(chip)
        strip.append(heading)

        faders = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        faders.append(Fader(
            stream, level, _('{channel} – stream mix').format(channel=name),
            caption=_('Stream'), mute_tooltip=_('Mute in stream'), muted=stream_muted))
        faders.append(Fader(
            headphones, level, _('{channel} – headphone mix').format(channel=name),
            caption=_('Me'), mute_tooltip=_('Mute in headphones')))
        strip.append(faders)

        if offset_ms is not None:
            strip.append(self._offset_controls(offset_ms))

    def _offset_controls(self, offset_ms):
        self._offset_ms = offset_ms
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, vexpand=True,
                      valign=Gtk.Align.END)
        box.add_css_class('strip-section')
        caption = Gtk.Label(label=_('Offset'))
        caption.add_css_class('caption')
        caption.add_css_class('dim-label')
        box.append(caption)

        row = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
        down = Gtk.Button(icon_name='list-remove-symbolic', tooltip_text=_('Decrease offset'))
        self._offset_label = Gtk.Label(width_chars=7)
        self._offset_label.add_css_class('monospace')
        up = Gtk.Button(icon_name='list-add-symbolic', tooltip_text=_('Increase offset'))
        for button in (down, up):
            button.add_css_class('circular')
            button.add_css_class('flat')
        down.connect('clicked', lambda _button: self._change_offset(-OFFSET_STEP_MS))
        up.connect('clicked', lambda _button: self._change_offset(OFFSET_STEP_MS))
        row.append(down)
        row.append(self._offset_label)
        row.append(up)
        box.append(row)

        self._change_offset(0)
        return box

    def _change_offset(self, delta):
        self._offset_ms = max(0, self._offset_ms + delta)
        self._offset_label.set_label(f'+{self._offset_ms} ms')
