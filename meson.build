project('ubuntu-start', version: '0.3.25', meson_version: '>= 1.0.0')


install_data('src/ubuntu_start.py', 'src/system_diagnostics.py', 'src/guide_search.py', 'src/first_run_state.py', install_dir: get_option('prefix') / 'libexec' / 'ubuntu-start')
i18n = import('i18n')
i18n.merge_file(
  input: 'data/se.danielnylander.UbuntuStart.desktop',
  output: 'se.danielnylander.UbuntuStart.desktop',
  type: 'desktop',
  po_dir: 'po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)
install_data('data/se.danielnylander.UbuntuStart.metainfo.xml', install_dir: get_option('datadir') / 'metainfo')
install_data('data/se.danielnylander.UbuntuStart.png', install_dir: get_option('datadir') / 'icons' / 'hicolor' / '512x512' / 'apps')

subdir('po')
