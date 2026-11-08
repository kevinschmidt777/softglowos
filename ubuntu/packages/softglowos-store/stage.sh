#!/usr/bin/env bash
# Bazaar (GPL-3.0, Flathub app store) built from source as "Softglow Store",
# with the home page, blocklist and settings of the Fedora image. Bazzite's
# Bazaar reads these from /usr/share/ublue-os/bazaar, so our files keep that
# path. Only what the user sees is renamed: the app ID stays Bazaar's, and
# its authors stay credited in the About dialog.
set -euo pipefail

VERSION=0.9.4
SHA256=b2521a998b84abf58b2b04a5d8bf29e41971d1f1cbaeef5cf079ba4bf516f5c2
URL=https://github.com/kolunmi/bazaar/archive/refs/tags/v$VERSION.tar.gz
CONFIG=/usr/share/ublue-os/bazaar
NAME="Softglow Store"

apt-get install -y -qq --no-install-recommends \
  xz-utils git meson ninja-build gcc pkgconf gettext python3-gi python3-babel libxml2-utils desktop-file-utils \
  appstream libglib2.0-dev-bin libgtk-4-dev libadwaita-1-dev libflatpak-dev libappstream-dev \
  libxmlb-dev libyaml-dev libsoup-3.0-dev libjson-glib-dev libglycin-2-dev \
  libglycin-gtk4-2-dev libwebkitgtk-6.0-dev libsecret-1-dev libproxy-dev \
  libmalcontent-0-dev libgtksourceview-5-dev libsystemd-dev libmd4c-dev >/dev/null

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Bazaar needs blueprint-compiler 0.20, Ubuntu has 0.19; it's only needed to
# build, so it runs from its source checkout (pinned to the tag's commit)
git -c advice.detachedHead=false clone -q --depth 1 -b v0.20.4 \
  https://gitlab.gnome.org/GNOME/blueprint-compiler.git "$tmp/blueprint" 2>/dev/null
[ "$(git -C "$tmp/blueprint" rev-parse HEAD)" = 31b62c24a72c1670d2d93dcdf2d130f1ae12778e ]
meson setup "$tmp/blueprint/build" "$tmp/blueprint" --prefix="$tmp/tools" | tail -n 5
meson install -C "$tmp/blueprint/build" >/dev/null
export PATH="$tmp/tools/bin:$PATH"
blueprint-compiler --version
curl -fsSL --retry 5 -o "$tmp/src.tar.gz" "$URL"
echo "$SHA256  $tmp/src.tar.gz" | sha256sum -c --quiet -
mkdir "$tmp/src"
tar -xzf "$tmp/src.tar.gz" -C "$tmp/src" --strip-components=1
cd "$tmp/src"

# The name in titles, menus and the app entry, in every language. Lines that
# credit Bazaar's authors or ask for donations to them keep the name.
find src po data -type f \( -name '*.blp' -o -name '*.c' -o -name '*.po' -o -name '*.in' \) \
  -exec sed -i -E "/Contributors|Mitwirkende|onat|Ko-Fi|spenden|kolunmi|Inspector/! \
    { /_ ?\(|C_ ?\(|^msgid|^msgstr|^Name=|<name>/ s/\bBazaar\b/$NAME/g }" {} +
grep -q "^Name=$NAME$" data/io.github.kolunmi.Bazaar.desktop.in

# Ubuntu's libdex is too old, so it's built along, statically
meson setup build --prefix=/usr --buildtype=release --force-fallback-for=libdex-1 \
  -Dlibdex:default_library=static -Dlibdex:introspection=disabled \
  -Dlibdex:docs=false -Dlibdex:examples=false -Dlibdex:tests=false \
  -Dlibdex:vapi=false -Dlibdex:pygobject=false \
  -Dhardcoded_main_config_path=$CONFIG/main.yaml \
  -Dhardcoded_blocklist_path=$CONFIG/blocklist.yaml \
  -Dhardcoded_content_config_path=$CONFIG/content.yaml | tail -n 15
meson compile -C build > "$tmp/compile.log" 2>&1 ||
  { grep -E -A8 "FAILED|error:" "$tmp/compile.log" | head -60; exit 1; }
DESTDIR="$DEST" meson install -C build --skip-subprojects >/dev/null
# The app and its widget library, without the library's headers and demo
rm -rf "$DEST/usr/include" "$DEST/usr/bin/bge-demo"
find "$DEST/usr/lib" \( -name libbge.so -o -name bge.pc \) -delete
find "$DEST/usr/lib" -type d -name pkgconfig -empty -delete

mkdir -p "$DEST$CONFIG"
cp "$SRC/files/system$CONFIG/"* "$DEST$CONFIG/"
ls "$DEST/usr/bin/bazaar" "$DEST/usr/share/applications/io.github.kolunmi.Bazaar.desktop"
