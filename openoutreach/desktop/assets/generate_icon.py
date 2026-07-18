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
    # Try to load from project logos directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    logo_path = project_root / "logos" / "icon.png"

    if not logo_path.exists():
        raise FileNotFoundError(
            f"Source logo not found at {logo_path}. "
            "Please ensure logos/icon.png exists."
        )

    return Image.open(logo_path)


def create_icon(size: int = 256) -> Image.Image:
    """Create desktop icon from source logo with green circle background."""
    # Load source logo
    source = load_source_logo()

    # Create output image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Draw green circle background
    draw = ImageDraw.Draw(img)
    color = (34, 197, 94, 255)  # Lengrowth green
    padding = int(size * 0.05)  # 5% padding
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=color
    )

    # Calculate logo size (should fit inside circle with some margin)
    logo_size = int(size * 0.7)  # Logo takes 70% of icon size
    logo_resized = source.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    # Center the logo
    x = (size - logo_size) // 2
    y = (size - logo_size) // 2

    # Paste logo on top of circle
    img.paste(logo_resized, (x, y), logo_resized if logo_resized.mode == 'RGBA' else None)

    return img


def create_ico(output_path: Path, sizes: list[int] | None = None):
    """Create Windows .ico file with multiple resolutions."""
    if sizes is None:
        sizes = [16, 24, 32, 48, 64, 128, 256]

    images = [create_icon(size) for size in sizes]
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )


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
        print(f"Note: .icns generation requires macOS. Saved as .png instead.")


if __name__ == "__main__":
    assets_dir = Path(__file__).parent

    print("Generating Lengrowth Linkedin desktop icons...")
    print(f"  Using source logo from: logos/icon.png")

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
