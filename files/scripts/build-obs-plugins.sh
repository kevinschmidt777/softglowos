#!/usr/bin/env bash
# Builds the OBS plugins that have no Fedora or Terra package from their
# source releases (both GPL-2.0, by Exeldro), against Fedora's
# obs-studio-devel so they match the OBS in the image:
#   Move Transition  animated transitions and moving sources between scenes
#   Source Record    records single sources or scenes on their own
# Versions are pinned with checksums; raise them on purpose. The build tools
# are only installed for this step.
set -euo pipefail

MOVE_VERSION=3.2.1
MOVE_SHA256=d7c599ffd65fb445a7e088b8c11cdbc6e5d135b23a3f866c3f045b0d571ce48a
MOVE_URL=https://github.com/exeldro/obs-move-transition/releases/download/$MOVE_VERSION/move-transition-$MOVE_VERSION-source.tar.xz
RECORD_VERSION=0.4.8
RECORD_SHA256=ad60c3cb88fec5b726fade90eeb872b527070822affc8d7fdd7cfb831c5a539e
RECORD_URL=https://github.com/exeldro/obs-source-record/archive/refs/tags/$RECORD_VERSION.tar.gz

BUILD_DEPS=(cmake gcc gcc-c++ obs-studio-devel)

missing=()
for pkg in "${BUILD_DEPS[@]}"; do
  rpm -q "$pkg" &>/dev/null || missing+=("$pkg")
done
tmp=$(mktemp -d)
cleanup() {
  rm -rf "$tmp"
  if [ ${#missing[@]} -gt 0 ]; then dnf5 -y remove "${missing[@]}"; fi
}
trap cleanup EXIT
if [ ${#missing[@]} -gt 0 ]; then dnf5 -y install "${missing[@]}"; fi

fetch() {  # url sha256 dir
  curl -fsSL -o "$tmp/src.tar" "$1"
  echo "$2  $tmp/src.tar" | sha256sum -c -
  mkdir -p "$3"
  tar -xf "$tmp/src.tar" -C "$3" --strip-components=1
}

fetch "$MOVE_URL" "$MOVE_SHA256" "$tmp/move"
cmake -S "$tmp/move" -B "$tmp/move/build" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_COMPILE_WARNING_AS_ERROR=OFF
cmake --build "$tmp/move/build" -j"$(nproc)"
cmake --install "$tmp/move/build"

fetch "$RECORD_URL" "$RECORD_SHA256" "$tmp/record"
cmake -S "$tmp/record" -B "$tmp/record/build" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr -DLIB_OUT_DIR=/lib64/obs-plugins
cmake --build "$tmp/record/build" -j"$(nproc)"
# Its older build setup also installs copies to /usr/obs-plugins and /usr/data,
# so stage it and take only the plugin and its translations
DESTDIR="$tmp/stage" cmake --install "$tmp/record/build"
install -D -m 755 "$tmp/stage/usr/lib64/obs-plugins/source-record.so" /usr/lib64/obs-plugins/source-record.so
mkdir -p /usr/share/obs/obs-plugins/source-record
cp -r "$tmp/stage/usr/share/obs/obs-plugins/source-record/locale" /usr/share/obs/obs-plugins/source-record/

# Fail the build if a plugin landed somewhere OBS doesn't look
ls /usr/lib64/obs-plugins/move-transition.so /usr/lib64/obs-plugins/source-record.so
ls -d /usr/share/obs/obs-plugins/move-transition /usr/share/obs/obs-plugins/source-record
