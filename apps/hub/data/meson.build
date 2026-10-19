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

# Daily update check with a notification (enabled in the image's recipe)
unit_conf = configuration_data()
unit_conf.set('pkgdatadir', pkgdatadir)
configure_file(
  input: 'systemd' / 'softglowos-update-check.service',
  output: 'softglowos-update-check.service',
  configuration: unit_conf,
  install_dir: get_option('prefix') / 'lib' / 'systemd' / 'user',
)
install_data(
  'systemd' / 'softglowos-update-check.timer',
  install_dir: get_option('prefix') / 'lib' / 'systemd' / 'user',
)

# Graphics card check on every login (enabled in the image's recipe)
configure_file(
  input: 'systemd' / 'softglowos-gpu-check.service',
  output: 'softglowos-gpu-check.service',
  configuration: unit_conf,
  install_dir: get_option('prefix') / 'lib' / 'systemd' / 'user',
)

# Readable password prompt for installing updates, none for the driver switch
configure_file(
  input: app_id + '.policy.in',
  output: app_id + '.policy',
  configuration: unit_conf,
  install_dir: get_option('datadir') / 'polkit-1' / 'actions',
)

# Setup assistant on the first login (exits right away once it's finished)
install_data(
  app_id + '.Setup.desktop',
  install_dir: get_option('sysconfdir') / 'xdg' / 'autostart',
)
