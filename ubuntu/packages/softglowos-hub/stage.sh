#!/usr/bin/env bash
# Builds the Hub (apps/hub) like files/scripts/install-hub.sh does on Fedora,
# minus the helpers for image updates, image switching by graphics card and
# Resolve via davincibox: the Hub hides those features without them.
set -euo pipefail

OPENRGB_PYTHON_VERSION=0.3.7
OPENRGB_PYTHON_SHA256=2188636e7a5831a8030abe34b234ede8d4a263ba02bc903d975eb55a80551833
OPENRGB_PYTHON_URL=https://files.pythonhosted.org/packages/68/d7/43deea59bc9a7bf4fd8e7fdc6695542d7c5a3034cf6627cd6c2121069920/openrgb_python-$OPENRGB_PYTHON_VERSION-py3-none-any.whl

apt-get install -y -qq --no-install-recommends \
  meson blueprint-compiler gettext desktop-file-utils libglib2.0-dev-bin \
  gtk-update-icon-cache pkgconf libglib2.0-dev gir1.2-gtk-4.0 gir1.2-adw-1 >/dev/null

build=$(mktemp -d)
trap 'rm -rf "$build"' EXIT
cp -a "$SRC/apps/hub" "$build/src"
meson setup "$build/out" "$build/src" --prefix=/usr
DESTDIR=$DEST meson install -C "$build/out" --quiet

hub=$DEST/usr/share/softglowos-hub
rm -f "$hub"/softglowos-{update,update-check,switch-channel,rebase,gpu-check,switch-gpu,resolve}
rm -f "$DEST"/usr/lib/systemd/user/softglowos-{update-check.service,update-check.timer,gpu-check.service}

# openrgb-python (GPL-3.0), the OpenRGB SDK client behind the Lighting page:
# Ubuntu doesn't package it either, so the same pinned wheel as on Fedora
curl -fsSL --retry 3 -o "$build/openrgb.whl" "$OPENRGB_PYTHON_URL"
echo "$OPENRGB_PYTHON_SHA256  $build/openrgb.whl" | sha256sum -c --quiet -
python3 -m zipfile -e "$build/openrgb.whl" "$hub/"

# Crash reports (only with the user's consent) and i2c for RGB on mainboards
# and RAM, shared with the Fedora image
for path in usr/libexec/softglowos-crash-reporter \
            usr/lib/systemd/user/softglowos-crash-reporter.service \
            usr/lib/modules-load.d/openrgb.conf; do
  install -D -m "$([ -x "$SRC/files/system/$path" ] && echo 755 || echo 644)" \
    "$SRC/files/system/$path" "$DEST/$path"
done

# Version and build date for the Hub's footer and bug reports
mkdir -p "$DEST/usr/share/softglowos"
cp "$SRC/VERSION" "$DEST/usr/share/softglowos/version"
date -u +%Y-%m-%d > "$DEST/usr/share/softglowos/build-date"
