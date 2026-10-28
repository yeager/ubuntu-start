project('ubuntu-start', version: '0.1.0', meson_version: '>= 1.0.0')


install_data('src/ubuntu_start.py', install_dir: get_option('prefix') / 'libexec' / 'ubuntu-start', rename: 'ubuntu_start.py')
i18n = import('i18n')
i18n.merge_file(
  input: 'data/se.nylander.UbuntuStart.desktop',
  output: 'se.nylander.UbuntuStart.desktop',
  type: 'desktop',
  po_dir: 'po',
  install: true,
  install_dir: get_option('datadir') / 'applications',
)
install_data('data/se.nylander.UbuntuStart.metainfo.xml', install_dir: get_option('datadir') / 'metainfo')
install_data('data/se.nylander.UbuntuStart.svg', install_dir: get_option('datadir') / 'icons' / 'hicolor' / 'scalable' / 'apps')

subdir('po')
