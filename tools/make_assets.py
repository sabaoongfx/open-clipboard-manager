"""Regenerates the app icon files in assets/ and the logo in public/ from winclipman.make_icon().

    python tools/make_assets.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from winclipman import make_icon  # noqa: E402

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <rect x="12" y="10" width="40" height="48" rx="6" fill="#3c78c8" stroke="#ffffff" stroke-width="2"/>
  <rect x="22" y="4" width="20" height="12" rx="4" fill="#e6e6e6" stroke="#5a5a5a" stroke-width="2"/>
  <g stroke="#ffffff" stroke-width="3" stroke-linecap="round">
    <line x1="20" y1="26" x2="44" y2="26"/><line x1="20" y1="36" x2="44" y2="36"/><line x1="20" y1="46" x2="44" y2="46"/>
  </g>
</svg>
"""


def main():
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "public"), exist_ok=True)
    icon = make_icon()
    icon.save(os.path.join(ROOT, "assets", "icon.png"))
    icon.save(os.path.join(ROOT, "assets", "icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)])
    with open(os.path.join(ROOT, "public", "open-clipboard-manager.svg"), "w", encoding="utf-8") as f:
        f.write(LOGO_SVG)
    print("wrote assets/icon.png, assets/icon.ico, public/open-clipboard-manager.svg")


if __name__ == "__main__":
    main()
