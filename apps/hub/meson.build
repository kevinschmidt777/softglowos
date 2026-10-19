project('softglowos-hub',
  version: '0.1.0',
  meson_version: '>= 1.0.0',
)

i18n = import('i18n')
gnome = import('gnome')
python = import('python')

app_id = 'com.softglowos.Hub'
pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()

subdir('data')
subdir('src')
subdir('po')

gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
