#!/usr/bin/env bash
# Runs inside the Ubuntu containers of build.sh, in two steps:
#   stage <package…>  on the target platform: fills /out/.stage/<package>
#   pack <package…>   on the host's own platform: dpkg-deb into /out
# Packing is separate because tar can't stat files under Rosetta's x86
# emulation on Apple Silicon; packing doesn't care about the architecture.
#
# Every package directory has a DEBIAN/ folder (control file with @VERSION@
# and @ARCH@, maintainer scripts), an optional root/ with files that only
# exist on Ubuntu, and an optional stage.sh that adds files from the shared
# repo (files/, apps/) and downloads or builds the rest.
set -euo pipefail

SRC=/src
OUT=/out
STAGES=$OUT/.stage
step=$1
shift

if [ "$step" = pack ]; then
  for package in "$@"; do
    # A directory as target names the file package_version_arch.deb
    dpkg-deb --root-owner-group -Zxz --build "$STAGES/$package" "$OUT/"
    rm -rf "${STAGES:?}/$package"
  done
  exit 0
fi

# VERSION from the repo plus the build date, so daily builds sort newer
VERSION="$(cat "$SRC/VERSION")~$(date -u +%Y%m%d%H%M)"

export DEBIAN_FRONTEND=noninteractive
# Every download of the stage scripts retries for a few minutes: GitHub's
# release downloads fail with 5xx now and then
printf 'retry = 10\nretry-all-errors\nretry-delay = 15\n' > ~/.curlrc
apt-get update -qq
# Tools the stage scripts use
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl unzip librsvg2-bin libglib2.0-bin python3 >/dev/null

for package in "$@"; do
  dir=$SRC/ubuntu/packages/$package
  stage=$STAGES/$package
  echo "==> $package $VERSION"
  rm -rf "$stage"
  mkdir -p "$stage"

  [ -d "$dir/root" ] && cp -a "$dir/root/." "$stage/"
  [ -x "$dir/stage.sh" ] && SRC=$SRC DEST=$stage PACKAGE_DIR=$dir "$dir/stage.sh"

  mkdir -p "$stage/DEBIAN"
  cp -a "$dir/DEBIAN/." "$stage/DEBIAN/"
  sed -i -e "s/@VERSION@/$VERSION/" -e "s/@ARCH@/$(dpkg --print-architecture)/" \
    "$stage/DEBIAN/control"
  if grep -q '@SHLIBS@' "$stage/DEBIAN/control"; then
    # The libraries the package's binaries link against, as Debian computes them
    apt-get install -y -qq --no-install-recommends dpkg-dev file >/dev/null
    elves=$(find "$stage" -type f -not -path '*/DEBIAN/*' -exec file {} + |
      awk -F: '/ELF/ { print $1 }')
    shlibs=$(cd "$(mktemp -d)" && mkdir debian && printf 'Source: x\n\nPackage: x\nArchitecture: any\n' > debian/control &&
      dpkg-shlibdeps -O --ignore-missing-info -l"$stage/usr/lib" \
        $(find "$stage" -name '*.so.*' -printf '-l%h\n' | sort -u) $elves 2>/dev/null |
      sed -n 's/^shlibs:Depends=//p')
    sed -i "s/@SHLIBS@/$shlibs/" "$stage/DEBIAN/control"
  fi
  chmod 755 "$stage/DEBIAN"/{preinst,postinst,prerm,postrm} 2>/dev/null || :
done
