"""Audio routing: which source goes to me, the stream and the chat mic (what
Discord hears). The mixer's mute buttons work on top of it."""
from gi.repository import Adw, Gtk

TARGETS = (
    ('monitor', 'audio-headphones-symbolic', _('Me')),
    ('stream', 'media-record-symbolic', _('Stream')),
    ('chat', 'audio-input-microphone-symbolic', _('Chat-Mic')),
)


class RoutingDialog(Adw.Dialog):
    def __init__(self, mixer, source_names):
        super().__init__(title=_('Audio routing'), content_width=480)
        self.mixer = mixer
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_child(toolbar)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=6, margin_bottom=24, margin_start=24, margin_end=24)
        toolbar.set_content(box)
        description = Gtk.Label(
            label=_('Where each sound goes. "Me" is what you hear, "Chat-Mic" what '
                    'Discord hears. The mute buttons in the mixer work on top.'),
            wrap=True, xalign=0)
        description.add_css_class('dim-label')
        box.append(description)

        grid = Gtk.Grid(column_spacing=24, row_spacing=10, halign=Gtk.Align.CENTER)
        for column, (_target, icon, label) in enumerate(TARGETS, 1):
            header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            header.append(Gtk.Image(icon_name=icon))
            caption = Gtk.Label(label=label)
            caption.add_css_class('caption')
            header.append(caption)
            grid.attach(header, column, 0, 1, 1)

        self.checks = {}
        for row, (source, name) in enumerate(source_names.items(), 1):
            grid.attach(Gtk.Label(label=name, xalign=0, hexpand=True), 0, row, 1, 1)
            for column, (target, _icon, label) in enumerate(TARGETS, 1):
                check = Gtk.CheckButton(halign=Gtk.Align.CENTER)
                check.update_property([Gtk.AccessibleProperty.LABEL], [f'{name}: {label}'])
                if mixer.routing_locked(source, target):
                    check.set_sensitive(False)
                    # Insensitive widgets show no tooltip, so it sits on a box around it
                    holder = Gtk.Box(halign=Gtk.Align.CENTER, tooltip_text=_(
                        'Discord would hear itself (echo)'))
                    holder.append(check)
                    grid.attach(holder, column, row, 1, 1)
                else:
                    check.handler = check.connect('toggled', self._on_toggled, source, target)
                    grid.attach(check, column, row, 1, 1)
                self.checks[source, target] = check
        box.append(grid)

        if len(mixer.linked_routes('browser')) > 1:
            hint = Gtk.Label(label=_('With the GoXLR, browser and console share one channel '
                                     '(Sample), so they switch together.'),
                             wrap=True, xalign=0)
            hint.add_css_class('dim-label')
            hint.add_css_class('caption')
            box.append(hint)

        reset = Gtk.Button(label=_('Reset'), halign=Gtk.Align.END)
        reset.connect('clicked', self._on_reset)
        box.append(reset)
        self._show()

    def _show(self):
        routes = self.mixer.routes()
        for (source, target), check in self.checks.items():
            if hasattr(check, 'handler'):
                with check.handler_block(check.handler):
                    check.set_active(routes[source][target])

    def _on_toggled(self, check, source, target):
        self.mixer.set_route(source, target, check.get_active())
        # Linked sources (browser and console with a GoXLR) follow along
        self._show()

    def _on_reset(self, _button):
        self.mixer.reset_routes()
        self._show()
