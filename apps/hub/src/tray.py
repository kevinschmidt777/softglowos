"""The mixer icon in the top bar.

GNOME shows tray icons through the AppIndicator extension, which speaks the
StatusNotifierItem protocol over D-Bus; its menu is a com.canonical.dbusmenu.
Both are small enough to serve here with Gio, no extra library. A click on
the icon calls on_activate (the mini mixer), the menu has "Open Hub"."""

import os

from gi.repository import Gio, GLib

ITEM_PATH = '/StatusNotifierItem'
MENU_PATH = '/StatusNotifierItem/Menu'
WATCHER = 'org.kde.StatusNotifierWatcher'
ICON = 'multimedia-volume-control-symbolic'

ITEM_XML = '''
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
    <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  </interface>
</node>'''

MENU_XML = '''
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <method name="GetLayout">
      <arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
      <arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" direction="in"/><arg type="as" direction="in"/>
      <arg type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in"/><arg type="s" direction="in"/>
      <arg type="v" direction="in"/><arg type="u" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/>
    </method>
    <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
    <method name="AboutToShowGroup">
      <arg type="ai" direction="in"/><arg type="ai" direction="out"/><arg type="ai" direction="out"/>
    </method>
    <signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
  </interface>
</node>'''


class Tray:
    def __init__(self, on_activate, on_open_hub):
        self._on_activate = on_activate
        self._items = {1: (_('Open Hub'), on_open_hub)}
        self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self._name = f'org.kde.StatusNotifierItem-{os.getpid()}-1'
        item = Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0]
        menu = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]
        self._registrations = [
            self._bus.register_object(ITEM_PATH, item, self._on_item_call, self._on_item_property),
            self._bus.register_object(MENU_PATH, menu, self._on_menu_call, self._on_menu_property),
        ]
        self._owner = Gio.bus_own_name_on_connection(
            self._bus, self._name, Gio.BusNameOwnerFlags.NONE, None, None)
        # Registers again whenever GNOME Shell (and with it the watcher) restarts
        self._watch = Gio.bus_watch_name_on_connection(
            self._bus, WATCHER, Gio.BusNameWatcherFlags.NONE, self._register, None)

    def stop(self):
        Gio.bus_unwatch_name(self._watch)
        Gio.bus_unown_name(self._owner)
        for registration in self._registrations:
            self._bus.unregister_object(registration)

    def _register(self, *_args):
        self._bus.call(WATCHER, '/StatusNotifierWatcher', WATCHER, 'RegisterStatusNotifierItem',
                       GLib.Variant('(s)', (self._name,)), None, Gio.DBusCallFlags.NONE,
                       -1, None, None)

    # StatusNotifierItem

    def _on_item_property(self, _bus, _sender, _path, _interface, name):
        return {
            'Category': GLib.Variant('s', 'Hardware'),
            'Id': GLib.Variant('s', 'softglowos-mixer'),
            'Title': GLib.Variant('s', _('Mixer')),
            'Status': GLib.Variant('s', 'Active'),
            'IconName': GLib.Variant('s', ICON),
            'ItemIsMenu': GLib.Variant('b', False),
            'Menu': GLib.Variant('o', MENU_PATH),
        }.get(name)

    def _on_item_call(self, _bus, _sender, _path, _interface, method, _params, invocation):
        if method == 'Activate':
            GLib.idle_add(self._on_activate)
        invocation.return_value(None)

    # Menu

    def _on_menu_property(self, _bus, _sender, _path, _interface, name):
        return {
            'Version': GLib.Variant('u', 3),
            'TextDirection': GLib.Variant('s', 'ltr'),
            'Status': GLib.Variant('s', 'normal'),
        }.get(name)

    def _properties(self, item_id):
        if item_id == 0:
            return {'children-display': GLib.Variant('s', 'submenu')}
        return {'label': GLib.Variant('s', self._items[item_id][0])}

    def _layout(self):
        children = [GLib.Variant('(ia{sv}av)', (item_id, self._properties(item_id), []))
                    for item_id in self._items]
        return (0, self._properties(0), children)

    def _on_menu_call(self, _bus, _sender, _path, _interface, method, params, invocation):
        if method == 'GetLayout':
            invocation.return_value(GLib.Variant('(u(ia{sv}av))', (1, self._layout())))
        elif method == 'GetGroupProperties':
            ids = params.unpack()[0] or list(self._items)
            invocation.return_value(GLib.Variant(
                '(a(ia{sv}))', ([(i, self._properties(i)) for i in ids if i in self._items or i == 0],)))
        elif method == 'GetProperty':
            item_id, name = params.unpack()
            value = self._properties(item_id).get(name, GLib.Variant('s', ''))
            invocation.return_value(GLib.Variant('(v)', (value,)))
        elif method == 'Event':
            item_id, event, _data, _time = params.unpack()
            if event == 'clicked' and item_id in self._items:
                GLib.idle_add(self._items[item_id][1])
            invocation.return_value(None)
        elif method == 'EventGroup':
            for item_id, event, _data, _time in params.unpack()[0]:
                if event == 'clicked' and item_id in self._items:
                    GLib.idle_add(self._items[item_id][1])
            invocation.return_value(GLib.Variant('(ai)', ([],)))
        elif method == 'AboutToShow':
            invocation.return_value(GLib.Variant('(b)', (False,)))
        elif method == 'AboutToShowGroup':
            invocation.return_value(GLib.Variant('(aiai)', ([], [])))
        else:
            invocation.return_value(None)
