from gi.repository import Adw, GLib, Gtk


class DevicePicker(Gtk.MenuButton):
    """A flat button showing the current device; clicking it lists the
    others. The list is read fresh every time it opens."""

    def __init__(self, list_devices, on_pick, markup=None, empty_label='', small=False):
        super().__init__()
        self.add_css_class('flat')
        self.add_css_class('device-picker')
        self._list_devices = list_devices
        self._on_pick = on_pick
        self._markup = markup
        self._empty_label = empty_label

        self._label = Gtk.Label(ellipsize=3, max_width_chars=24)
        if small:
            self._label.add_css_class('caption')
            self._label.add_css_class('dim-label')
        self.set_child(self._label)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class('boxed-list')
        self._list.connect('row-activated', self._on_row_activated)
        popover = Gtk.Popover(child=self._list)
        popover.connect('show', lambda _popover: self._fill())
        self.set_popover(popover)

    def set_device(self, device):
        name = device.description if device else self._empty_label
        if self._markup:
            self._label.set_markup(self._markup.format(
                device=GLib.markup_escape_text(name)))
        else:
            self._label.set_label(name)

    def _fill(self):
        child = self._list.get_first_child()
        while child:
            self._list.remove(child)
            child = self._list.get_first_child()
        for device in self._list_devices():
            row = Adw.ActionRow(title=GLib.markup_escape_text(device.description),
                                activatable=True)
            row.device = device
            self._list.append(row)

    def _on_row_activated(self, _list, row):
        self.get_popover().popdown()
        self._on_pick(row.device)
        self.set_device(row.device)


class EqDialog(Adw.Dialog):
    """Graphic EQ for the microphone: one vertical slider per band."""

    def __init__(self, bands, gains, gain_range, on_change):
        super().__init__(title=_('Microphone EQ'), content_width=640)
        self._on_change = on_change
        self._scales = []

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        reset = Gtk.Button(label=_('Reset'))
        reset.connect('clicked', self._on_reset)
        header.pack_start(reset)
        toolbar.add_top_bar(header)

        row = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, homogeneous=True,
                      margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        for band, (frequency, gain) in enumerate(zip(bands, gains)):
            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            value = Gtk.Label()
            value.add_css_class('monospace')
            value.add_css_class('caption')
            scale = Gtk.Scale(
                orientation=Gtk.Orientation.VERTICAL, inverted=True, draw_value=False,
                height_request=200,
                adjustment=Gtk.Adjustment(lower=-gain_range, upper=gain_range,
                                          step_increment=0.5, page_increment=1, value=gain),
            )
            scale.add_mark(0, Gtk.PositionType.RIGHT, None)
            scale.add_css_class('fader')
            scale.update_property([Gtk.AccessibleProperty.LABEL],
                                  [_('{frequency} band').format(frequency=_format_hz(frequency))])
            scale.connect('value-changed', self._on_value_changed, band, value)
            self._show_value(scale, value)
            label = Gtk.Label(label=_format_hz(frequency))
            label.add_css_class('caption')
            label.add_css_class('dim-label')
            column.append(value)
            column.append(scale)
            column.append(label)
            row.append(column)
            self._scales.append(scale)

        toolbar.set_content(row)
        self.set_child(toolbar)

    @staticmethod
    def _show_value(scale, label):
        label.set_label(f'{scale.get_value():+.1f}')

    def _on_value_changed(self, scale, band, label):
        self._show_value(scale, label)
        self._on_change(band, scale.get_value())

    def _on_reset(self, _button):
        for scale in self._scales:
            scale.set_value(0)


def _format_hz(frequency):
    if frequency >= 1000:
        return f'{frequency / 1000:g} kHz'
    return f'{frequency:g} Hz'
