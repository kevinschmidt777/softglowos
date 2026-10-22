from gi.repository import Gdk, GLib, GObject, Gtk

FADER_HEIGHT = 184
# Ignore outside updates this long after the user moved a fader, so values
# echoed back by the GoXLR while dragging don't make the knob jump.
USER_HOLD_US = 400_000
OFFSET_STEP_MS = 10
OFFSET_MAX_MS = 2000


class Fader(Gtk.Box):
    """A vertical fader with level meter, value, optional mute button and caption.

    Calls on_change(value) and on_mute(muted) when the user changes it;
    set_state() updates it from outside without calling them."""

    def __init__(self, accessible_name, caption=None, mute_tooltip=None, unit='',
                 on_change=None, on_mute=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                         halign=Gtk.Align.CENTER)
        self._unit = unit
        self._on_change = on_change
        self._on_mute = on_mute
        self._muted = False
        self._level = 0.0
        self._touched = 0

        controls = Gtk.Box(spacing=3, halign=Gtk.Align.CENTER)
        self.meter = Gtk.LevelBar(orientation=Gtk.Orientation.VERTICAL, inverted=True,
                                  min_value=0, max_value=1, height_request=FADER_HEIGHT)
        self.meter.add_css_class('meter')
        for offset in ('low', 'high', 'full'):
            self.meter.remove_offset_value(offset)
        controls.append(self.meter)

        self.scale = Gtk.Scale(
            orientation=Gtk.Orientation.VERTICAL, inverted=True, draw_value=False,
            height_request=FADER_HEIGHT,
            adjustment=Gtk.Adjustment(lower=0, upper=100, step_increment=1,
                                      page_increment=10),
        )
        self.scale.add_css_class('fader')
        self.scale.update_property([Gtk.AccessibleProperty.LABEL], [accessible_name])
        self._value_handler = self.scale.connect('value-changed', self._on_value_changed)
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
            self._mute_handler = self.mute_button.connect('toggled', self._on_mute_toggled)
            self.append(self.mute_button)

        if caption:
            caption_label = Gtk.Label(label=caption)
            caption_label.add_css_class('caption')
            caption_label.add_css_class('dim-label')
            self.append(caption_label)

        self.set_state(0, False)

    def set_state(self, value, muted):
        if GLib.get_monotonic_time() - self._touched > USER_HOLD_US:
            with self.scale.handler_block(self._value_handler):
                self.scale.set_value(value)
        if self.mute_button:
            with self.mute_button.handler_block(self._mute_handler):
                self.mute_button.set_active(muted)
        self._show(muted)

    def set_level(self, level):
        """Level of the signal before this fader, 0..1."""
        self._level = level
        self._update_meter()

    def _show(self, muted):
        self._muted = muted
        if muted:
            self.add_css_class('muted')
        else:
            self.remove_css_class('muted')
        if self.mute_button:
            self.mute_button.set_icon_name(
                'audio-volume-muted-symbolic' if muted else 'audio-volume-high-symbolic')
        self.value_label.set_label(f'{round(self.scale.get_value())}{self._unit}')
        self._update_meter()

    def _update_meter(self):
        self.meter.set_value(0 if self._muted else self._level * self.scale.get_value() / 100)

    def _on_value_changed(self, scale):
        self._touched = GLib.get_monotonic_time()
        self._show(self._muted)
        if self._on_change:
            self._on_change(round(scale.get_value()))

    def _on_mute_toggled(self, button):
        self._show(button.get_active())
        if self._on_mute:
            self._on_mute(button.get_active())


def _strip_box(**kwargs):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, **kwargs)
    box.add_css_class('card')
    box.add_css_class('mixer-strip')
    return box


def _heading(text):
    label = Gtk.Label(label=text)
    label.add_css_class('heading')
    return label


class OffsetControl(Gtk.Box):
    """Delay in 10 ms steps (− / value / +) at the bottom of a strip."""

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, caption):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.add_css_class('strip-section')
        self.add_css_class('offset-control')
        label = Gtk.Label(label=caption)
        label.add_css_class('caption')
        label.add_css_class('dim-label')
        self.append(label)

        row = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER)
        down = Gtk.Button(icon_name='list-remove-symbolic', tooltip_text=_('Decrease offset'))
        self._label = Gtk.Label(width_chars=7)
        self._label.add_css_class('monospace')
        self._label.add_css_class('caption')
        up = Gtk.Button(icon_name='list-add-symbolic', tooltip_text=_('Increase offset'))
        for button in (down, up):
            button.add_css_class('circular')
            button.add_css_class('flat')
        down.connect('clicked', lambda _button: self._change(-OFFSET_STEP_MS))
        up.connect('clicked', lambda _button: self._change(OFFSET_STEP_MS))
        row.append(down)
        row.append(self._label)
        row.append(up)
        self.append(row)
        self.set_ms(0)

    def set_ms(self, ms):
        self._ms = ms
        self._label.set_label(f'+{ms} ms')

    def _change(self, delta):
        ms = min(OFFSET_MAX_MS, max(0, self._ms + delta))
        self.set_ms(ms)
        self.emit('changed', ms)


class MicStrip(Gtk.Box):
    """The microphone input: device, level, filters, EQ, mute and offset."""

    __gsignals__ = {
        'level-changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'mute-changed': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        'filter-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        'eq-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'setup-requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'offset-changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    FILTERS = (('rnnoise', _('Noise suppression')),
               ('gate', _('Noise gate')),
               ('compressor', _('Compressor')))

    def __init__(self, device_picker):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        strip = _strip_box(spacing=14, width_request=208, vexpand=True)
        self.append(strip)

        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          halign=Gtk.Align.CENTER)
        heading.append(_heading(_('Microphone')))
        device_picker.set_halign(Gtk.Align.CENTER)
        heading.append(device_picker)
        self.badge = Gtk.MenuButton(visible=False, halign=Gtk.Align.CENTER)
        self.badge.add_css_class('fader-badge')
        heading.append(self.badge)
        strip.append(heading)

        self.fader = Fader(_('Microphone level'), unit=' %',
                           on_change=lambda value: self.emit('level-changed', value))
        strip.append(self.fader)

        filters = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        filters.add_css_class('strip-section')
        self._switches = {}
        for filter_id, label in self.FILTERS:
            row = Gtk.Box(spacing=8)
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            switch.update_property([Gtk.AccessibleProperty.LABEL], [label])
            handler = switch.connect('notify::active', self._on_switch, filter_id)
            self._switches[filter_id] = (switch, handler)
            row.append(switch)
            filters.append(row)
        buttons = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, margin_top=4)
        eq_button = Gtk.Button(label=_('Open EQ'))
        eq_button.connect('clicked', lambda _button: self.emit('eq-requested'))
        buttons.append(eq_button)
        setup_button = Gtk.Button(label=_('Mic setup'))
        setup_button.connect('clicked', lambda _button: self.emit('setup-requested'))
        buttons.append(setup_button)
        filters.append(buttons)
        strip.append(filters)

        self.mute_button = Gtk.ToggleButton(label=_('Mute'), valign=Gtk.Align.END,
                                            vexpand=True)
        self.mute_button.add_css_class('mute-button')
        self._mute_handler = self.mute_button.connect('toggled', self._on_mute_toggled)
        strip.append(self.mute_button)

        # Only the stream: Discord and the headphones keep the mic undelayed
        self.offset = OffsetControl(_('Offset (stream)'))
        self.offset.connect('changed', lambda _control, ms: self.emit('offset-changed', ms))
        strip.append(self.offset)

    def set_badge(self, text):
        self.badge.set_visible(text is not None)
        if text is not None:
            self.badge.set_label(text)

    def set_state(self, value, muted):
        self.fader.set_state(value, muted)
        with self.mute_button.handler_block(self._mute_handler):
            self.mute_button.set_active(muted)
        self._show_mute(muted)

    def set_filters(self, filters):
        for filter_id, (switch, handler) in self._switches.items():
            with switch.handler_block(handler):
                switch.set_active(filters.get(filter_id, False))

    def set_filter_available(self, filter_id, available, tooltip=None):
        switch, _handler = self._switches[filter_id]
        switch.set_sensitive(available)
        switch.set_tooltip_text(tooltip)

    def _on_switch(self, switch, _pspec, filter_id):
        self.emit('filter-changed', filter_id, switch.get_active())

    def _show_mute(self, muted):
        self.mute_button.set_label(_('Muted – unmute') if muted else _('Mute'))

    def _on_mute_toggled(self, button):
        muted = button.get_active()
        self._show_mute(muted)
        self.fader.set_state(self.fader.scale.get_value(), muted)
        self.emit('mute-changed', muted)


class ChannelStrip(Gtk.Box):
    """One mixer channel with a stream fader and a headphone fader. Apps can be
    dragged from one channel onto another."""

    __gsignals__ = {
        'fader-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, int)),
        'mute-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, bool)),
        'app-dropped': (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        'offset-changed': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
    }

    def __init__(self, channel_id, name, device_picker=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        self.channel_id = channel_id
        self._apps = {}
        self.strip = _strip_box(spacing=12, width_request=112, vexpand=True)
        self.append(self.strip)

        self._heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                                halign=Gtk.Align.CENTER, height_request=48)
        self._heading.append(_heading(name))
        self.badge = Gtk.MenuButton(visible=False, halign=Gtk.Align.CENTER)
        self.badge.add_css_class('fader-badge')
        self._heading.append(self.badge)
        if device_picker:
            device_picker.set_halign(Gtk.Align.CENTER)
            self._heading.append(device_picker)
        self._chips = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._heading.append(self._chips)
        self.strip.append(self._heading)

        faders = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        self.faders = {
            'stream': Fader(_('{channel} – stream mix').format(channel=name),
                            caption=_('Stream'), mute_tooltip=_('Mute in stream'),
                            on_change=lambda v: self.emit('fader-changed', 'stream', v),
                            on_mute=lambda m: self.emit('mute-changed', 'stream', m)),
            'monitor': Fader(_('{channel} – headphone mix').format(channel=name),
                             caption=_('Me'), mute_tooltip=_('Mute in headphones'),
                             on_change=lambda v: self.emit('fader-changed', 'monitor', v),
                             on_mute=lambda m: self.emit('mute-changed', 'monitor', m)),
        }
        for fader in self.faders.values():
            faders.append(fader)
        self.strip.append(faders)

        self.offset = OffsetControl(_('Offset'))
        self.offset.set_vexpand(True)
        self.offset.set_valign(Gtk.Align.END)
        self.offset.connect('changed', lambda _control, ms: self.emit('offset-changed', ms))
        self.strip.append(self.offset)

        drop = Gtk.DropTarget.new(GObject.TYPE_PYOBJECT, Gdk.DragAction.MOVE)
        drop.connect('drop', self._on_drop)
        drop.connect('enter', lambda *_args: self._highlight(True) or Gdk.DragAction.MOVE)
        drop.connect('leave', lambda *_args: self._highlight(False))
        self.add_controller(drop)

    def set_apps(self, apps):
        """Shows the apps playing into this channel as draggable chips."""
        child = self._chips.get_first_child()
        while child:
            self._chips.remove(child)
            child = self._chips.get_first_child()
        for app in apps:
            chip = Gtk.Label(label=app.name, halign=Gtk.Align.CENTER,
                             tooltip_text=_('Drag onto another channel'))
            chip.add_css_class('app-chip')
            drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.connect('prepare', lambda _source, _x, _y, a=app:
                         Gdk.ContentProvider.new_for_value(a))
            chip.add_controller(drag)
            self._chips.append(chip)

    def set_badge(self, text):
        self.badge.set_visible(text is not None)
        if text is not None:
            self.badge.set_label(text)

    def _highlight(self, on):
        if on:
            self.strip.add_css_class('drop-target')
        else:
            self.strip.remove_css_class('drop-target')

    def _on_drop(self, _target, app, _x, _y):
        self._highlight(False)
        self.emit('app-dropped', app)
        return True
