#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow>=10.0.0"]
# ///
"""Generate the Zoolog PWA icons from the native viewer's AppIcon.icns
(the snail-writing-a-scroll artwork)."""
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"
ICNS = HERE.parent / "native-viewer" / "Zoolog" / "Resources" / "AppIcon.icns"


def load_source() -> Image.Image:
    """Extract the 1024px PNG from the .icns and return it as RGBA."""
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "AppIcon.iconset"
        subprocess.run(["iconutil", "-c", "iconset", str(ICNS), "-o", str(iconset)],
                       check=True)
        best = max(iconset.glob("*.png"), key=lambda p: p.stat().st_size)
        return Image.open(best).convert("RGBA")


def bg_color(src: Image.Image):
    return src.getpixel((4, 4))[:3]


def square(src: Image.Image, size: int) -> Image.Image:
    """Resized art flattened onto its own cream background (opaque)."""
    canvas = Image.new("RGB", (size, size), bg_color(src))
    art = src.resize((size, size), Image.LANCZOS)
    canvas.paste(art, (0, 0), art)
    return canvas


def maskable(src: Image.Image, size: int, scale: float = 0.80) -> Image.Image:
    """Art inset within the safe zone so platform masks never clip it."""
    canvas = Image.new("RGB", (size, size), bg_color(src))
    inner = int(size * scale)
    art = src.resize((inner, inner), Image.LANCZOS)
    off = (size - inner) // 2
    canvas.paste(art, (off, off), art)
    return canvas


def main():
    ICONS.mkdir(exist_ok=True)
    src = load_source()
    square(src, 192).save(ICONS / "icon-192.png")
    square(src, 512).save(ICONS / "icon-512.png")
    square(src, 180).save(ICONS / "apple-touch-icon.png")
    maskable(src, 512).save(ICONS / "maskable-512.png")
    print("Wrote icon-192, icon-512, apple-touch-icon, maskable-512 from", ICNS.name)


if __name__ == "__main__":
    main()
