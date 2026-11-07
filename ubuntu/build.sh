#!/usr/bin/env bash
# Builds the SoftglowOS .deb packages for Ubuntu in an Ubuntu 26.04
# container, so it works the same on a Mac and in GitHub Actions. The
# container runs on the host's own architecture: our packages so far are
# Architecture: all, and tar fails under x86 emulation on Apple Silicon.
#   ubuntu/build.sh                  every package
#   ubuntu/build.sh softglowos-base  only that one
# The packages land in ubuntu/out/.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
PACKAGES=("$@")
[ ${#PACKAGES[@]} -gt 0 ] || PACKAGES=($(ls "$REPO/ubuntu/packages"))

mkdir -p "$REPO/ubuntu/out"
docker run --rm \
  -v "$REPO:/src:ro" -v "$REPO/ubuntu/out:/out" \
  ubuntu:26.04 /src/ubuntu/build-in-container.sh "${PACKAGES[@]}"
