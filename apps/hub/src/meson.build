blueprints = custom_target('blueprints',
  input: files(
    'window.blp',
    'mixer-page.blp',
  ),
  output: [
    'window.ui',
    'mixer-page.ui',
  ],
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTDIR@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources('hub',
  'hub.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('pkgdatadir', pkgdatadir)
conf.set('localedir', get_option('prefix') / get_option('localedir'))

configure_file(
  input: 'softglowos-hub.in',
  output: 'softglowos-hub',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

install_data(
  '__init__.py',
  'main.py',
  'window.py',
  'mixer_page.py',
  'strips.py',
  'widgets.py',
  'mic_setup.py',
  'audio.py',
  'goxlr.py',
  'software.py',
  'software_page.py',
  'resolve.py',
  'affinity.py',
  'devices_page.py',
  'settings_page.py',
  'updates.py',
  'gpu.py',
  'bug_report.py',
  'setup.py',
  'tray.py',
  'mini_mixer.py',
  'mixer_actions.py',
  'crash_reports.py',
  'lighting.py',
  'lighting_page.py',
  install_dir: pkgdatadir / 'hub',
)

install_data(
  'softglowos-resolve',
  'softglowos-affinity',
  'softglowos-update',
  'softglowos-update-check',
  'softglowos-gpu-check',
  'softglowos-switch-gpu',
  'softglowos-switch-channel',
  'softglowos-rebase',
  'softglowos-lighting-save',
  install_dir: pkgdatadir,
  install_mode: 'rwxr-xr-x',
)
