"""Generate icons for desktop app in all required formats.

Uses the Lengrowth logo from logos/icon.png as source.

Generates:
- icon.png (256x256) - Main icon for Linux/general use
- icon.ico - Multi-resolution Windows icon
- icon.icns - macOS icon bundle (requires iconutil on macOS)
- icon-{size}.png - Various sizes for different contexts
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw


def load_source_logo() -> Image.Image:
    """Load the source logo from logos/icon.png."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    logo_path = project_root / "logos" / "icon.png"

    if not logo_path.exists():
        raise FileNotFoundError(
            f"Source logo not found at {logo_path}. "
            "Please ensure logos/icon.png exists."
        )

    return Image.open(logo_path).convert("RGBA")


def create_icon(size: int = 256) -> Image.Image:
    """Resize source logo to a square icon with a circular mask.

    The source logo already has the correct brand background, so we just
    resize it to a square and clip it to a circle so it looks clean in the
    Windows/macOS system tray.
    """
    source = load_source_logo()

    # Resize to a square (the source is nearly square already)
    resized = source.resize((size, size), Image.Resampling.LANCZOS)

    # Apply a circular mask so it looks like a proper app icon
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size - 1, size - 1], fill=255)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(resized, (0, 0))
    result.putalpha(mask)

    return result


def create_ico(output_path: Path, sizes: list[int] | None = None):
    """Create Windows .ico file with multiple resolutions.

    PIL ICO save requires a single source image; it handles resizing internally.
    Always downscale from the largest size for best quality.
    """
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]

    source = create_icon(max(sizes))
    source.save(output_path, format="ICO", sizes=[(s, s) for s in sizes])


def create_icns(output_path: Path):
    """Create macOS .icns file.

    On macOS, uses iconutil. On other platforms, creates a basic icns structure.
    """
    if sys.platform == "darwin":
        import subprocess
        import tempfile

        icon_sizes = {
            "icon_16x16.png": 16,
            "icon_16x16@2x.png": 32,
            "icon_32x32.png": 32,
            "icon_32x32@2x.png": 64,
            "icon_128x128.png": 128,
            "icon_128x128@2x.png": 256,
            "icon_256x256.png": 256,
            "icon_256x256@2x.png": 512,
            "icon_512x512.png": 512,
            "icon_512x512@2x.png": 1024,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            iconset_dir = Path(tmpdir) / "icon.iconset"
            iconset_dir.mkdir()

            for name, size in icon_sizes.items():
                icon = create_icon(size)
                icon.save(iconset_dir / name)

            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
                check=True,
            )
    else:
        icon = create_icon(256)
        icon.save(output_path.with_suffix(".png"))
        print("Note: .icns generation requires macOS. Saved as .png instead.")


if __name__ == "__main__":
    assets_dir = Path(__file__).parent

    print("Generating Lengrowth Linkedin desktop icons...")
    print("  Using source logo from: logos/icon.png")

    # Main PNG icon (256x256)
    icon = create_icon(256)
    icon.save(assets_dir / "icon.png")
    print("  icon.png (256x256)")

    # PNG sizes for various uses
    for size in [16, 24, 32, 48, 64, 128, 256, 512]:
        icon = create_icon(size)
        icon.save(assets_dir / f"icon-{size}.png")
    print("  icon-{size}.png (16-512)")

    # Windows ICO
    create_ico(assets_dir / "icon.ico")
    print("  icon.ico (multi-resolution)")

    # macOS ICNS
    create_icns(assets_dir / "icon.icns")
    print("  icon.icns (macOS bundle)")

    print("Done!")
