"""Mic setup: with a GoXLR its mic type (48 V phantom power) and gain plus
the GoXLR profiles, without one the input level of the microphone."""
from gi.repository import Adw, Gio, GLib, Gtk

from .goxlr import MIC_GAIN_MAX_DB, MIC_PROFILE_SUFFIX, MIC_TYPES, PROFILE_SUFFIX
from .strips import USER_HOLD_US

MIC_TYPE_NAMES = {
    'Dynamic': _('Dynamic'),
    'Condenser': _('Condenser (48 V phantom power)'),
    'Jack': _('Jack (3.5 mm)'),
}
INPUT_LEVEL_MAX = 150
SAVED_LABEL_SECONDS = 2


def _slider_row(title, upper, unit, on_change):
    """A row with a slider and its value, e.g. "Gain  ───●───  40 dB"."""
    row = Adw.ActionRow(title=title)
    value = Gtk.Label(width_chars=6, xalign=1)
    value.add_css_class('monospace')
    value.add_css_class('dim-label')
    scale = Gtk.Scale(hexpand=True, draw_value=False, valign=Gtk.Align.CENTER,
                      width_request=220,
                      adjustment=Gtk.Adjustment(lower=0, upper=upper, step_increment=1,
                                                page_increment=6))
    scale.update_property([Gtk.AccessibleProperty.LABEL], [title])

    def changed(scale):
        row.touched = GLib.get_monotonic_time()
        value.set_label(f'{round(scale.get_value())} {unit}')
        on_change(round(scale.get_value()))

    row.touched = 0
    row.handler = scale.connect('value-changed', changed)
    row.scale = scale
    row.value = value
    row.add_suffix(scale)
    row.add_suffix(value)
    return row


def _set_slider(row, number, unit):
    """Shows a value from outside, unless the user is dragging the slider."""
    if GLib.get_monotonic_time() - row.touched < USER_HOLD_US:
        return
    with row.scale.handler_block(row.handler):
        row.scale.set_value(number)
    row.value.set_label(f'{round(number)} {unit}')


class MicSetupDialog(Adw.Dialog):
    def __init__(self, mixer):
        super().__init__(title=_('Mic setup'), content_width=520)
        self.mixer = mixer
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        page = Adw.PreferencesPage()
        toolbar.set_content(page)
        self.set_child(toolbar)

        if mixer.mic_type() is None:
            group = Adw.PreferencesGroup(
                description=_('How loud your microphone comes in. Turn it up if it is '
                              'too quiet, down if it distorts.'))
            self.level_row = _slider_row(_('Input level'), INPUT_LEVEL_MAX, '%',
                                         mixer.set_mic_input_level)
            group.add(self.level_row)
            page.add(group)
            level = mixer.mic_input_level()
            self.level_row.set_sensitive(level is not None)
            _set_slider(self.level_row, level or 0, '%')
            return

        mic = Adw.PreferencesGroup(
            title=_('Microphone'),
            description=_('Condenser turns on 48 V phantom power. Condenser microphones '
                          'need it, and so do inline preamps like the FetHead.'))
        self.type_row = Adw.ComboRow(title=_('Microphone type'),
                                     model=Gtk.StringList.new(
                                         [MIC_TYPE_NAMES[t] for t in MIC_TYPES]))
        self._type_handler = self.type_row.connect('notify::selected', self._on_type)
        mic.add(self.type_row)
        self.gain_row = _slider_row(_('Gain'), MIC_GAIN_MAX_DB, 'dB', mixer.set_mic_gain_db)
        mic.add(self.gain_row)
        page.add(mic)

        profiles = Adw.PreferencesGroup(
            title=_('Profiles'),
            description=_('The GoXLR keeps its settings in two profiles: one for the '
                          'device, one for the microphone. Profiles from the GoXLR app on '
                          'Windows or the GoXLR Utility can be imported.'))
        self.profile_rows = {}
        for mic_profile, title in ((False, _('Device profile')),
                                   (True, _('Microphone profile'))):
            row = Adw.ComboRow(title=title)
            row.handler = row.connect('notify::selected', self._on_profile, mic_profile)
            self.profile_rows[mic_profile] = row
            profiles.add(row)
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, margin_top=12)
        import_button = Gtk.Button(label=_('Import…'))
        import_button.connect('clicked', self._on_import)
        self.save_button = Gtk.Button(label=_('Save'))
        self.save_button.connect('clicked', self._on_save)
        buttons.append(import_button)
        buttons.append(self.save_button)
        profiles.add(buttons)
        page.add(profiles)

        # Profiles loaded or the desk changed something: show it
        self._changed = mixer.connect('changed', lambda _mixer: self._refresh())
        self.connect('closed', lambda _dialog: mixer.disconnect(self._changed))
        self._refresh()

    def _refresh(self):
        if self.mixer.mic_type() is None:
            return  # GoXLR gone while open
        with self.type_row.handler_block(self._type_handler):
            self.type_row.set_selected(MIC_TYPES.index(self.mixer.mic_type()))
        _set_slider(self.gain_row, self.mixer.mic_gain_db(), 'dB')
        for mic_profile, row in self.profile_rows.items():
            names = self.mixer.profiles(mic_profile)
            current = self.mixer.profile(mic_profile)
            if current not in names:
                names.append(current)
            with row.handler_block(row.handler):
                row.set_model(Gtk.StringList.new(names))
                row.set_selected(names.index(current))

    def _on_type(self, row, _pspec):
        self.mixer.set_mic_type(MIC_TYPES[row.get_selected()])

    def _on_profile(self, row, _pspec, mic_profile):
        name = row.get_selected_item().get_string()
        if name != self.mixer.profile(mic_profile):
            self.mixer.load_profile(name, mic_profile)

    def _on_import(self, _button):
        profiles = Gtk.FileFilter(name=_('GoXLR profiles'))
        for suffix in (PROFILE_SUFFIX, MIC_PROFILE_SUFFIX):
            profiles.add_suffix(suffix.lstrip('.'))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(profiles)
        dialog = Gtk.FileDialog(title=_('Import GoXLR profile'), filters=filters)
        dialog.open(self.get_root(), None, self._on_import_chosen)

    def _on_import_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
        except GLib.Error:
            return  # cancelled
        if not self.mixer.import_profile(file.get_path()):
            alert = Adw.AlertDialog(heading=_('Not a GoXLR profile'),
                                    body=_('Choose a .goxlr or .goxlrMicProfile file.'))
            alert.add_response('ok', _('OK'))
            alert.present(self)

    def _on_save(self, _button):
        self.mixer.save_profiles()
        self.save_button.set_label(_('Saved'))
        GLib.timeout_add_seconds(SAVED_LABEL_SECONDS,
                                 lambda: self.save_button.set_label(_('Save')) or
                                 GLib.SOURCE_REMOVE)
