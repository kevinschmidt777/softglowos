#!/usr/bin/env bash
# Builds the OBS plugins that have no Fedora or Terra package from their
# source releases (all GPL-2.0), against Fedora's obs-studio-devel so they
# match the OBS in the image:
#   Move Transition    animated transitions and moving sources between scenes
#   Source Record      records single sources or scenes on their own
#   Source Clone       shows one source again without duplicating it
#   Shaderfilter       custom shader effects on sources and scenes
#   Composite Blur     blur filters, also with masks
#   Advanced Masks     shape and image masks on sources
#   Stroke Glow Shadow outlines, glows and shadows on sources
# Versions are pinned with checksums; raise them on purpose. The build tools
# are only installed for this step.
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

BUILD_DEPS=(cmake gcc gcc-c++ libcurl-devel obs-studio-devel qt6-qtbase-devel qt6-qtsvg-devel)

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

build_standard() {  # url sha256 name [cmake flags]: for plugins on OBS's plugin template
  local url=$1 sha256=$2 name=$3
  shift 3
  fetch "$url" "$sha256" "$tmp/$name"
  cmake -S "$tmp/$name" -B "$tmp/$name/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_COMPILE_WARNING_AS_ERROR=OFF "$@"
  cmake --build "$tmp/$name/build" -j"$(nproc)"
  cmake --install "$tmp/$name/build"
}

build_standard "$MOVE_URL" "$MOVE_SHA256" move
build_standard "$CLONE_URL" "$CLONE_SHA256" clone
build_standard "$BLUR_URL" "$BLUR_SHA256" blur
build_standard "$MASKS_URL" "$MASKS_SHA256" masks -DENABLE_QT=ON -DENABLE_FRONTEND_API=ON
build_standard "$GLOW_URL" "$GLOW_SHA256" glow

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

# Same older build setup, so again only the plugin and its data
fetch "$SHADER_URL" "$SHADER_SHA256" "$tmp/shader"
cmake -S "$tmp/shader" -B "$tmp/shader/build" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr -DLIB_OUT_DIR=/lib64/obs-plugins \
  -DCMAKE_C_FLAGS=-Wno-error=discarded-qualifiers
cmake --build "$tmp/shader/build" -j"$(nproc)"
DESTDIR="$tmp/shader-stage" cmake --install "$tmp/shader/build"
install -D -m 755 "$tmp/shader-stage/usr/lib64/obs-plugins/obs-shaderfilter.so" /usr/lib64/obs-plugins/obs-shaderfilter.so
cp -r "$tmp/shader-stage/usr/share/obs/obs-plugins/obs-shaderfilter" /usr/share/obs/obs-plugins/

# Fail the build if a plugin landed somewhere OBS doesn't look
for plugin in move-transition source-record source-clone obs-shaderfilter \
  obs-composite-blur obs-advanced-masks obs-stroke-glow-shadow; do
  ls "/usr/lib64/obs-plugins/$plugin.so"
  ls -d "/usr/share/obs/obs-plugins/$plugin"
done
