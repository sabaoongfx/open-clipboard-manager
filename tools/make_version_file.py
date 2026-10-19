"""Writes the Windows version resource (the "Details" tab of a file's properties) for PyInstaller.

    python tools/make_version_file.py <output file> <original file name>

The product name, company and version come from platform_base, so every build carries the same values.
Code-signing services such as SignPath require the product name and version to be set consistently.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from platform_base import APP_NAME, APP_VERSION  # noqa: E402

COMPANY = "sabaoongfx"
COPYRIGHT = "Copyright (c) 2026 sabaoongfx. MIT License."


def version_tuple(version):
    """'0.3.0' -> (0, 3, 0, 0): Windows file versions always have four numbers."""
    parts = [int(p) for p in version.split(".")]
    if len(parts) > 4 or any(p < 0 or p > 65535 for p in parts):
        raise ValueError(f"not a usable file version: {version!r}")
    return tuple(parts + [0] * (4 - len(parts)))


def build(original_filename, version=APP_VERSION, name=APP_NAME):
    """The text of a PyInstaller version file."""
    numbers = version_tuple(version)
    dotted = ".".join(str(n) for n in numbers)
    strings = (
        ("CompanyName", COMPANY),
        ("FileDescription", name),
        ("FileVersion", dotted),
        ("InternalName", name.replace(" ", "-")),
        ("LegalCopyright", COPYRIGHT),
        ("OriginalFilename", original_filename),
        ("ProductName", name),
        ("ProductVersion", dotted),
    )
    rows = ",\n".join(f"        StringStruct({key!r}, {value!r})" for key, value in strings)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
{rows}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    output, original = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(build(original))
    print(f"wrote {output} for {original} ({APP_NAME} {APP_VERSION})")


if __name__ == "__main__":
    main()
