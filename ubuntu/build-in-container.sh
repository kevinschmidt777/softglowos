#!/usr/bin/env bash
# Runs inside the Ubuntu container of build.sh: every package directory has a
# DEBIAN/ folder (control file with @VERSION@, maintainer scripts), an
# optional root/ with files that only exist on Ubuntu, and an optional
# stage.sh that adds files from the shared repo (files/, apps/) and
# downloads. The result is packed with dpkg-deb.
set -euo pipefail

SRC=/src
OUT=/out
# VERSION from the repo plus the build date, so daily builds sort newer
VERSION="$(cat "$SRC/VERSION")~$(date -u +%Y%m%d%H%M)"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# Tools the stage scripts use
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl unzip librsvg2-bin libglib2.0-bin python3 >/dev/null

for package in "$@"; do
  dir=$SRC/ubuntu/packages/$package
  stage=$(mktemp -d)
  echo "==> $package $VERSION"

  [ -d "$dir/root" ] && cp -a "$dir/root/." "$stage/"
  [ -x "$dir/stage.sh" ] && SRC=$SRC DEST=$stage PACKAGE_DIR=$dir "$dir/stage.sh"

  mkdir -p "$stage/DEBIAN"
  cp -a "$dir/DEBIAN/." "$stage/DEBIAN/"
  sed -i "s/@VERSION@/$VERSION/" "$stage/DEBIAN/control"
  chmod 755 "$stage/DEBIAN"/{preinst,postinst,prerm,postrm} 2>/dev/null || :

  # A directory as target names the file package_version_arch.deb
  dpkg-deb --root-owner-group -Zxz --build "$stage" "$OUT/"
  rm -rf "$stage"
done
