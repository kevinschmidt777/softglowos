#!/usr/bin/env bash
# Bazzite already disables its terra-mesa repo, but only through
# /etc/dnf/repos.override.d. bootc-image-builder reads /etc/yum.repos.d alone
# when it resolves the installer packages for the ISO and fails on the repo's
# file:// GPG key. Write the same state into the repo file itself.
set -euo pipefail

sed -i 's/^enabled=1$/enabled=0/' /etc/yum.repos.d/terra-mesa.repo
