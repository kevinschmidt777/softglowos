#!/usr/bin/env bash
# OBS's launcher and our OBS plugins, built against the OBS from the OBS
# team's PPA (Ubuntu's plugin packages belong to Ubuntu's own OBS):
#   Move Transition    animated transitions and moving sources between scenes
#   Source Record      records single sources or scenes on their own
#   Source Clone       shows one source again without duplicating it
#   Shaderfilter       custom shader effects on sources and scenes
#   Composite Blur     blur filters, also with masks
#   Advanced Masks     shape and image masks on sources
#   Stroke Glow Shadow outlines, glows and shadows on sources
#   vkcapture          game capture for Vulkan and OpenGL games
# All GPL-2.0, pinned with checksums; raise them on purpose.
# Plus our own softglowos-defaults (in this folder): capture cards and webcams
# without buffering, so a monitor switch can't push them out of sync.
set -euo pipefail

MOVE_VERSION=3.2.1
MOVE_SHA256=d7c599ffd65fb445a7e088b8c11cdbc6e5d135b23a3f866c3f045b0d571ce48a
MOVE_URL=https://github.com/exeldro/obs-move-transition/releases/download/$MOVE_VERSION/move-transition-$MOVE_VERSION-source.tar.xz
RECORD_VERSION=0.4.8
RECORD_SHA256=ad60c3cb88fec5b726fade90eeb872b527070822affc8d7fdd7cfb831c5a539e
RECORD_URL=https://github.com/exeldro/obs-source-record/archive/refs/tags/$RECORD_VERSION.tar.gz
CLONE_VERSION=0.2.3
CLONE_SHA256=d7fd00b6eb25df991b8864125cc97b2825a403d7ebc48f673289ef6d499ddc49
CLONE_URL=https://github.com/exeldro/obs-source-clone/releases/download/$CLONE_VERSION/source-clone-$CLONE_VERSION-source.tar.xz
SHADER_VERSION=2.6.1
SHADER_SHA256=e39aeca71aefafa8a0da8fb6df12291566c0f678b71358020916c4f033857a27
SHADER_URL=https://github.com/exeldro/obs-shaderfilter/archive/refs/tags/$SHADER_VERSION.tar.gz
# Composite Blur, Advanced Masks and Stroke Glow Shadow come from FiniteSingularity
FINITE_URL=https://github.com/FiniteSingularity
BLUR_VERSION=1.6.1
BLUR_SHA256=1db4ce775e26332ccfc7ec8feb7e8bc01716d6f86a50942171ed94dfbc5571dc
BLUR_URL=$FINITE_URL/obs-composite-blur/releases/download/v$BLUR_VERSION/obs-composite-blur-$BLUR_VERSION-source.tar.xz
MASKS_VERSION=1.6.1
MASKS_SHA256=4cfedd5e8ad7f73131e0d480b70fe92d110d38848412c075bc5f653f724d55ad
MASKS_URL=$FINITE_URL/obs-advanced-masks/releases/download/v$MASKS_VERSION/obs-advanced-masks-$MASKS_VERSION-source.tar.xz
GLOW_VERSION=1.6.1
GLOW_SHA256=30599db40834100988c3b89a1ac6ad823c13c3905b1af8e802fd1a18d1818b8f
GLOW_URL=$FINITE_URL/obs-stroke-glow-shadow/releases/download/v$GLOW_VERSION/obs-stroke-glow-shadow-$GLOW_VERSION-source.tar.xz
VKCAPTURE_VERSION=1.5.6
VKCAPTURE_SHA256=4f0eecd574cf4765bf8a4c5e09b7c764d1c4a9128e6c6fea99e2c6474c494fe0
VKCAPTURE_URL=https://github.com/nowrep/obs-vkcapture/archive/refs/tags/v$VKCAPTURE_VERSION.tar.gz

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

# Our own plugin, one C file (the PPA's libobs.pc leaves out the obs folder)
gcc -shared -fPIC -O2 -std=gnu17 -fvisibility=hidden -Wall -Wextra -Werror -DHAVE_OBSCONFIG_H \
  -I/usr/include/obs -o "$tmp/softglowos-defaults.so" \
  "$PACKAGE_DIR/softglowos-defaults/softglowos-defaults.c" -lobs
install -D -m 644 "$tmp/softglowos-defaults.so" "$DEST$plugins/softglowos-defaults.so"

# The first-start launcher
install -D -m 755 "$SRC/files/system/usr/bin/softglowos-obs" "$DEST/usr/bin/softglowos-obs"

# Fail the build if a plugin landed somewhere OBS doesn't look
for plugin in move-transition source-record source-clone obs-shaderfilter \
  obs-composite-blur obs-advanced-masks obs-stroke-glow-shadow linux-vkcapture softglowos-defaults; do
  ls "$DEST$plugins/$plugin.so"
done
