#!/usr/bin/env bash
# Build a .deb from the PyInstaller one-folder build.
#   packaging/linux/build-deb.sh <one-folder build dir> <version> <output.deb>
# Run from the repository root (it reads packaging/linux/*, assets/icon-256.png and LICENSE).
set -euo pipefail

dist="$1"
version="$2"
out="$3"

root="$(mktemp -d)"
install -d "$root/DEBIAN" "$root/opt/open-clipboard-manager" "$root/usr/bin" \
  "$root/usr/share/applications" "$root/usr/share/icons/hicolor/256x256/apps" \
  "$root/usr/share/doc/open-clipboard-manager"

cp -a "$dist/." "$root/opt/open-clipboard-manager/"
ln -s /opt/open-clipboard-manager/open-clipboard-manager "$root/usr/bin/open-clipboard-manager"
install -m 644 packaging/linux/open-clipboard-manager.desktop "$root/usr/share/applications/"
install -m 644 assets/icon-256.png "$root/usr/share/icons/hicolor/256x256/apps/open-clipboard-manager.png"
install -m 644 LICENSE "$root/usr/share/doc/open-clipboard-manager/copyright"

cat > "$root/DEBIAN/control" <<EOF
Package: open-clipboard-manager
Version: $version
Section: utils
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.35), libx11-6, libxft2, libfontconfig1
Recommends: xclip | wl-clipboard, xdotool
Maintainer: sabaoongfx <sabaoongfx@users.noreply.github.com>
Homepage: https://github.com/sabaoongfx/open-clipboard-manager
Description: Clipboard history manager for text and images
 Remembers what you copy and brings it back with a global hotkey (Super+V on
 X11), in a window styled after Open Task Manager. Reads the clipboard through
 xclip or wl-clipboard and pastes with xdotool (X11), wtype or ydotool
 (Wayland). Everything stays on your computer.
EOF

# The files are installed as root-owned regardless of who builds the package.
dpkg-deb --root-owner-group --build "$root" "$out"
rm -rf "$root"
dpkg-deb --info "$out"
