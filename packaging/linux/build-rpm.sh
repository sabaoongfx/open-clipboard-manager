#!/usr/bin/env bash
# Build an .rpm from the PyInstaller one-folder build (works on a Debian/Ubuntu machine with `rpm` installed).
#   packaging/linux/build-rpm.sh <one-folder build dir> <version> <output.rpm>
# Run from the repository root (it reads packaging/linux/*, assets/icon-256.png and LICENSE).
set -euo pipefail

dist="$(realpath "$1")"
version="$2"
out="$3"
repo="$(pwd)"

top="$(mktemp -d)"
mkdir -p "$top"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

cat > "$top/SPECS/open-clipboard-manager.spec" <<EOF
Name:       open-clipboard-manager
Version:    $version
Release:    1
Summary:    Clipboard history manager for text and images
License:    MIT
URL:        https://github.com/sabaoongfx/open-clipboard-manager
BuildArch:  x86_64
# The PyInstaller folder bundles its own Python and libraries: don't let rpm scan them for dependencies.
AutoReqProv: no
Requires:   glibc, libX11, libXft, fontconfig
Recommends: xclip, xdotool

%global debug_package %{nil}
%global __os_install_post %{nil}

%description
Remembers what you copy and brings it back with a global hotkey (Super+V on X11), in a window styled
after Open Task Manager. Reads the clipboard through xclip or wl-clipboard and pastes with xdotool (X11),
wtype or ydotool (Wayland). Everything stays on your computer.

%install
install -d %{buildroot}/opt/open-clipboard-manager %{buildroot}/usr/bin \\
  %{buildroot}/usr/share/applications %{buildroot}/usr/share/icons/hicolor/256x256/apps
cp -a "$dist/." %{buildroot}/opt/open-clipboard-manager/
ln -s /opt/open-clipboard-manager/open-clipboard-manager %{buildroot}/usr/bin/open-clipboard-manager
install -m 644 "$repo/packaging/linux/open-clipboard-manager.desktop" %{buildroot}/usr/share/applications/
install -m 644 "$repo/assets/icon-256.png" %{buildroot}/usr/share/icons/hicolor/256x256/apps/open-clipboard-manager.png
install -D -m 644 "$repo/LICENSE" %{buildroot}/usr/share/licenses/open-clipboard-manager/LICENSE

%files
/opt/open-clipboard-manager
/usr/bin/open-clipboard-manager
/usr/share/applications/open-clipboard-manager.desktop
/usr/share/icons/hicolor/256x256/apps/open-clipboard-manager.png
%license /usr/share/licenses/open-clipboard-manager/LICENSE
EOF

rpmbuild -bb --define "_topdir $top" "$top/SPECS/open-clipboard-manager.spec"
cp "$top"/RPMS/x86_64/*.rpm "$out"
rpm -qpi "$out"
rpm -qpl "$out" | head -n 8
rm -rf "$top"
