#!/usr/bin/env bash
# OBS's launcher and the OBS plugins of the Bazzite image, built against the
# OBS from the OBS team's PPA. Fedora packages some plugins and builds the
# rest (files/scripts/build-obs-plugins.sh); Ubuntu's plugin packages belong
# to Ubuntu's own OBS, so here all of them are built.
set -euo pipefail

# Same pinned versions and checksums as the Fedora image
eval "$(grep -E '^(MOVE|RECORD|CLONE|SHADER|FINITE|BLUR|MASKS|GLOW)_[A-Z0-9]+=' \
  "$SRC/files/scripts/build-obs-plugins.sh")"
VKCAPTURE_VERSION=1.5.6
VKCAPTURE_SHA256=4f0eecd574cf4765bf8a4c5e09b7c764d1c4a9128e6c6fea99e2c6474c494fe0
VKCAPTURE_URL=https://github.com/nowrep/obs-vkcapture/archive/refs/tags/v$VKCAPTURE_VERSION.tar.gz
DROIDCAM_VERSION=2.5.1
DROIDCAM_SHA256=f02dc570c0dfc3c83124d3b9758555c9b0f93d76633d2c19537154e74ddf1d2f
DROIDCAM_URL=https://github.com/dev47apps/droidcam-obs-plugin/archive/refs/tags/$DROIDCAM_VERSION.tar.gz

# OBS from the PPA, with the source this package installs on the system
cp "$PACKAGE_DIR/root/etc/apt/sources.list.d/obs-studio.sources" /etc/apt/sources.list.d/
cp "$PACKAGE_DIR/root/usr/share/keyrings/obs-studio-ppa.asc" /usr/share/keyrings/
sed -i 's/^Components: main.*/Components: main restricted universe multiverse/' \
  /etc/apt/sources.list.d/ubuntu.sources
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  obs-studio xz-utils cmake make g++ pkgconf libcurl4-openssl-dev libsimde-dev \
  qt6-base-dev qt6-base-private-dev qt6-svg-dev \
  libvulkan-dev libwayland-dev libegl-dev libgl-dev libx11-dev libxcb1-dev libdrm-dev \
  libturbojpeg0-dev libimobiledevice-dev libusbmuxd-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev >/dev/null

arch_dir=$(dpkg-architecture -qDEB_HOST_MULTIARCH 2>/dev/null || gcc -dumpmachine)
# OBS 33 loads third-party plugins from obs-modules/plugins (obs-plugins only
# for now, as a legacy path); their builds still install to the old place
plugins=/usr/lib/$arch_dir/obs-modules/plugins
data=/usr/share/obs/obs-modules/plugins
echo "OBS $(dpkg-query -W -f='${Version}' obs-studio)"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# OBS 33 marks APIs these releases still use as deprecated, and some of them
# build with -Werror
export CFLAGS=-Wno-error=deprecated-declarations CXXFLAGS=-Wno-error=deprecated-declarations

fetch() {  # url sha256 dir
  curl -fsSL --retry 3 -o "$tmp/src.tar" "$1"
  echo "$2  $tmp/src.tar" | sha256sum -c --quiet -
  mkdir -p "$3"
  tar -xf "$tmp/src.tar" -C "$3" --strip-components=1
}

build_cmake() {  # url sha256 name [cmake flags]
  local url=$1 sha256=$2 name=$3
  shift 3
  fetch "$url" "$sha256" "$tmp/$name"
  cmake -S "$tmp/$name" -B "$tmp/$name/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_COMPILE_WARNING_AS_ERROR=OFF "$@" >/dev/null
  cmake --build "$tmp/$name/build" -j"$(nproc)" >/dev/null
  DESTDIR="$tmp/$name/stage" cmake --install "$tmp/$name/build" >/dev/null
}

take_plugin() {  # name stage: only the plugin and its data, wherever its build put them
  local name=$1 stage=$2
  install -D -m 644 "$(find "$stage" -name "$name.so" \( -path '*obs-plugins*' -o -path '*obs-modules*' \) | head -n1)" \
    "$DEST$plugins/$name.so"
  local share
  share=$(find "$stage" -type d \( -path "*/obs-plugins/$name" -o -path "*/obs-modules/plugins/$name" \) \
    -path '*/share/*' | head -n1)
  if [ -n "$share" ]; then
    mkdir -p "$DEST$data"
    cp -r "$share" "$DEST$data/"
  fi
}

build_cmake "$MOVE_URL" "$MOVE_SHA256" move-transition
take_plugin move-transition "$tmp/move-transition/stage"
build_cmake "$CLONE_URL" "$CLONE_SHA256" source-clone
take_plugin source-clone "$tmp/source-clone/stage"
build_cmake "$BLUR_URL" "$BLUR_SHA256" obs-composite-blur
take_plugin obs-composite-blur "$tmp/obs-composite-blur/stage"
build_cmake "$MASKS_URL" "$MASKS_SHA256" obs-advanced-masks -DENABLE_QT=ON -DENABLE_FRONTEND_API=ON
take_plugin obs-advanced-masks "$tmp/obs-advanced-masks/stage"
build_cmake "$GLOW_URL" "$GLOW_SHA256" obs-stroke-glow-shadow
take_plugin obs-stroke-glow-shadow "$tmp/obs-stroke-glow-shadow/stage"
build_cmake "$RECORD_URL" "$RECORD_SHA256" source-record -DLIB_OUT_DIR="/lib/$arch_dir/obs-plugins"
take_plugin source-record "$tmp/source-record/stage"
build_cmake "$SHADER_URL" "$SHADER_SHA256" obs-shaderfilter -DLIB_OUT_DIR="/lib/$arch_dir/obs-plugins" \
  -DCMAKE_C_FLAGS="$CFLAGS -Wno-error=discarded-qualifiers"
take_plugin obs-shaderfilter "$tmp/obs-shaderfilter/stage"

# Game Capture: the plugin, the Vulkan layer and OpenGL hook that games load,
# and the obs-gamecapture launchers, all as the project installs them
build_cmake "$VKCAPTURE_URL" "$VKCAPTURE_SHA256" obs-vkcapture
take_plugin linux-vkcapture "$tmp/obs-vkcapture/stage"
rm -rf "$tmp"/obs-vkcapture/stage/usr/lib/*/obs-plugins "$tmp/obs-vkcapture/stage/usr/share/obs"
cp -a "$tmp/obs-vkcapture/stage/." "$DEST/"

# DroidCam (phone as webcam), built with its own Makefile
fetch "$DROIDCAM_URL" "$DROIDCAM_SHA256" "$tmp/droidcam"
make -C "$tmp/droidcam" -j"$(nproc)" \
  LIBOBS_INCLUDES=/usr/include/obs FFMPEG_INCLUDES="/usr/include/$arch_dir" \
  LIBUSBMUXD=libusbmuxd-2.0 LIBIMOBILEDEV=libimobiledevice-1.0 >/dev/null
install -D -m 644 "$tmp/droidcam/build/droidcam-obs.so" "$DEST$plugins/droidcam-obs.so"
mkdir -p "$DEST$data/droidcam-obs"
cp -r "$tmp/droidcam/data/." "$DEST$data/droidcam-obs/"

# The first-start launcher, shared with the Fedora image
install -D -m 755 "$SRC/files/system/usr/bin/softglowos-obs" "$DEST/usr/bin/softglowos-obs"

# Fail the build if a plugin landed somewhere OBS doesn't look
for plugin in move-transition source-record source-clone obs-shaderfilter \
  obs-composite-blur obs-advanced-masks obs-stroke-glow-shadow linux-vkcapture droidcam-obs; do
  ls "$DEST$plugins/$plugin.so"
done
