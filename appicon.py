"""The app icon, drawn with Pillow.

It lives in its own module (and imports nothing but Pillow) so tools/make_assets.py can render the icon files
on a machine without a display, which importing the app itself would not allow on Linux.
"""
from PIL import Image, ImageDraw


def make_icon():
    """A 64 x 64 RGBA clipboard icon."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 10, 52, 58), 6, fill=(60, 120, 200), outline=(255, 255, 255), width=2)
    d.rounded_rectangle((22, 4, 42, 16), 4, fill=(230, 230, 230), outline=(90, 90, 90), width=2)
    for y in (26, 36, 46):
        d.line((20, y, 44, y), fill=(255, 255, 255), width=3)
    return img
