#!/usr/bin/env bash
# Builds the SoftglowOS .deb packages for Ubuntu in an Ubuntu 26.04
# container, so it works the same on a Mac and in GitHub Actions.
#   ubuntu/build.sh                  every package
#   ubuntu/build.sh softglowos-base  only that one
#   PLATFORM=linux/arm64 ubuntu/build.sh   for the arm64 test VM
# SoftglowOS itself is x86_64 (linux/amd64, the default); on Apple Silicon
# that runs under Docker Desktop's Rosetta emulation. Packing then happens in
# a second container on the host's own platform (see build-in-container.sh).
# The packages land in ubuntu/out/.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
PLATFORM=${PLATFORM:-linux/amd64}
PACKAGES=("$@")
[ ${#PACKAGES[@]} -gt 0 ] || PACKAGES=($(ls "$REPO/ubuntu/packages"))

case $(uname -m) in
  arm64|aarch64) NATIVE=linux/arm64 ;;
  *) NATIVE=linux/amd64 ;;
esac

mkdir -p "$REPO/ubuntu/out"
run() {  # platform step
  # The host's network: Docker's own DNS on GitHub's runners stopped
  # resolving archive.ubuntu.com (2026-11-11)
  docker run --rm --platform "$1" --network host \
    -v "$REPO:/src:ro" -v "$REPO/ubuntu/out:/out" \
    ubuntu:26.04 /src/ubuntu/build-in-container.sh "$2" "${PACKAGES[@]}"
}
run "$PLATFORM" stage
run "$NATIVE" pack
