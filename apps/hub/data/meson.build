i18n.merge_file(
  input: app_id + '.desktop.in',
  output: app_id + '.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)

install_data(
  'icons' / app_id + '.svg',
  install_dir: get_option('datadir') / 'icons' / 'hicolor' / 'scalable' / 'apps',
)

# Mixer icon in the top bar
install_data(
  'icons' / app_id + '.Mixer-symbolic.svg',
  install_dir: get_option('datadir') / 'icons' / 'hicolor' / 'symbolic' / 'apps',
)

unit_conf = configuration_data()
unit_conf.set('pkgdatadir', pkgdatadir)

# OpenRGB server for the Lighting page (enabled per user by the Hub)
configure_file(
  input: 'systemd' / 'softglowos-lighting.service',
  output: 'softglowos-lighting.service',
  configuration: unit_conf,
  install_dir: get_option('prefix') / 'lib' / 'systemd' / 'user',
)

# Setup assistant on the first login (exits right away once it's finished)
install_data(
  app_id + '.Setup.desktop',
  install_dir: get_option('sysconfdir') / 'xdg' / 'autostart',
)

# Lets D-Bus start the Hub for a mixer action (StreamController plugin)
dbus_conf = configuration_data()
dbus_conf.set('bindir', get_option('prefix') / get_option('bindir'))
configure_file(
  input: app_id + '.service.in',
  output: app_id + '.service',
  configuration: dbus_conf,
  install_dir: get_option('datadir') / 'dbus-1' / 'services',
)

# Mixer icon in the top bar (switched off per user from the Hub's settings)
install_data(
  app_id + '.Tray.desktop',
  install_dir: get_option('sysconfdir') / 'xdg' / 'autostart',
)
