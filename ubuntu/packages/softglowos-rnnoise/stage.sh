#!/usr/bin/env bash
# RNNoise's LADSPA plugin (noise-suppression-for-voice, GPL-3.0), built from
# source, so it also runs in the arm64 test VM. Into
# /usr/lib/ladspa, which PipeWire's filter-chain searches on Ubuntu.
set -euo pipefail

VERSION=1.10
SHA256=6e0c11aeb8392891750b0243c2ba695dab07654bf3f4e01adbed927b36cc690a
URL=https://github.com/werman/noise-suppression-for-voice/archive/refs/tags/v$VERSION.tar.gz

apt-get install -y -qq --no-install-recommends cmake make g++ >/dev/null

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 -o "$tmp/src.tar.gz" "$URL"
echo "$SHA256  $tmp/src.tar.gz" | sha256sum -c --quiet -
tar xzf "$tmp/src.tar.gz" -C "$tmp"

cmake -S "$tmp/noise-suppression-for-voice-$VERSION" -B "$tmp/build" \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_FOR_RELEASE=ON -DBUILD_TESTS=OFF \
  -DBUILD_LADSPA_PLUGIN=ON -DBUILD_VST_PLUGIN=OFF -DBUILD_VST3_PLUGIN=OFF \
  -DBUILD_LV2_PLUGIN=OFF -DBUILD_AU_PLUGIN=OFF -DBUILD_AUV3_PLUGIN=OFF \
  -DBUILD_RTCD=$([ "$(dpkg --print-architecture)" = amd64 ] && echo ON || echo OFF) >/dev/null
cmake --build "$tmp/build" -j "$(nproc)" >/dev/null

plugin=$(find "$tmp/build" -name librnnoise_ladspa.so | head -n1)
install -D -m 644 "$plugin" "$DEST/usr/lib/ladspa/librnnoise_ladspa.so"
strip --strip-unneeded "$DEST/usr/lib/ladspa/librnnoise_ladspa.so"
