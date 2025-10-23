"""
Collage generation module.

Handles tile selection, render generation, ImageMagick montage, and manifest creation.

Configuration:
- Set COLLAGEN_DATA_DIR environment variable for data location
- Dev: defaults to /tmp/collagen-local
- Prod: export COLLAGEN_DATA_DIR=/mnt/efs
"""

import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter


def get_tiles_oldest_first(tiles_dir: Path, limit: Optional[int] = None) -> List[Path]:
    """
    Get tiles sorted by modification time (oldest first).

    Args:
        tiles_dir: Path to tiles directory
        limit: Optional limit on number of tiles to return

    Returns:
        List of Path objects sorted oldest first
    """
    tiles = list(tiles_dir.glob("*.png"))
    tiles.sort(key=lambda p: p.stat().st_mtime)

    if limit:
        tiles = tiles[:limit]

    return tiles


def extract_email_from_tile(tile_path: Path) -> Optional[str]:
    """
    Extract email from tile EXIF metadata.

    Uses exiftool to read UserComment field.

    Args:
        tile_path: Path to PNG tile

    Returns:
        Email address or None if not found
    """
    try:
        result = subprocess.run(
            ["exiftool", "-UserComment", "-s", "-s", "-s", str(tile_path)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        return None

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def check_email_duplicates(tiles: List[Path], logger=None) -> Dict[str, int]:
    """
    Check for duplicate emails across tiles.

    Args:
        tiles: List of tile paths
        logger: Optional logger for warnings

    Returns:
        Dict mapping email -> count (only emails with count > 1)
    """
    emails = []

    for tile in tiles:
        email = extract_email_from_tile(tile)
        if email:
            emails.append(email)

    # Find duplicates
    email_counts = Counter(emails)
    duplicates = {email: count for email, count in email_counts.items() if count > 1}

    if duplicates and logger:
        logger.warning(f"Found {len(duplicates)} email addresses with multiple tiles:")
        for email, count in duplicates.items():
            logger.warning(f"  {email}: {count} tiles")

    return duplicates


def generate_renders(tiles: List[Path], renders_dir: Path, cell_width: int, cell_height: int):
    """
    Generate render tiles at specific grid dimensions.

    Args:
        tiles: List of tile paths (300×400 PNGs)
        renders_dir: Output directory for renders
        cell_width: Target width for render tiles
        cell_height: Target height for render tiles
    """
    renders_dir.mkdir(parents=True, exist_ok=True)

    for tile in tiles:
        render_path = renders_dir / tile.name

        # Use ImageMagick convert to resize
        # -geometry: resize to exact dimensions
        # -gravity center: center the image if aspect doesn't match
        # -extent: crop/pad to exact size
        subprocess.run(
            [
                "convert",
                str(tile),
                "-resize", f"{cell_width}x{cell_height}^",  # ^ = fill, may crop
                "-gravity", "center",
                "-extent", f"{cell_width}x{cell_height}",
                str(render_path)
            ],
            check=True
        )


def generate_montage(renders_dir: Path, output_path: Path, cols: int, rows: int,
                    padding_h: int, padding_v: int, clip_h: int, clip_v: int, target_size: int):
    """
    Generate collage using ImageMagick montage.

    Args:
        renders_dir: Directory containing render tiles
        output_path: Output path for master PNG
        cols: Grid columns
        rows: Grid rows
        padding_h: Horizontal padding (total, will be split across edges)
        padding_v: Vertical padding (total, will be split across edges)
        clip_h: Horizontal clipping (total, will be split across edges)
        clip_v: Vertical clipping (total, will be split across edges)
        target_size: Target dimension (4096 for 4K)
    """
    # Get list of renders sorted by name (same order as tiles)
    renders = sorted(renders_dir.glob("*.png"))

    # Create montage with transparent background
    cmd = [
        "montage",
        *[str(r) for r in renders],
        "-tile", f"{cols}x{rows}",
        "-geometry", "+0+0",  # No spacing between tiles
        "-background", "none",  # Transparent background
        str(output_path)
    ]

    subprocess.run(cmd, check=True)

    # Apply padding/clipping to reach target_size
    if padding_h > 0 or padding_v > 0:
        # Add transparent padding (border)
        subprocess.run(
            [
                "convert",
                str(output_path),
                "-bordercolor", "none",
                "-border", f"{padding_h//2}x{padding_v//2}",
                str(output_path)
            ],
            check=True
        )

    if clip_h > 0 or clip_v > 0:
        # Crop from center
        subprocess.run(
            [
                "convert",
                str(output_path),
                "-gravity", "center",
                "-crop", f"{target_size}x{target_size}+0+0",
                "+repage",
                str(output_path)
            ],
            check=True
        )


def generate_derivatives(master_path: Path, output_dir: Path, collage_width: int, collage_height: int,
                        sizes: List[int] = [4096, 1024]):
    """
    Generate JPEG derivatives at various sizes.

    Crops to actual collage dimensions, converts transparency to white background.

    Args:
        master_path: Path to 4096.png (may have transparent padding to reach 4096×4096)
        output_dir: Output directory
        collage_width: Actual collage width (e.g., 3840)
        collage_height: Actual collage height (e.g., 4096)
        sizes: List of max dimensions for derivatives (default: [4096, 1024])
    """
    for size in sizes:
        output_path = output_dir / f"{size}.jpg"

        # Calculate dimensions preserving aspect ratio
        scale = min(size / collage_width, size / collage_height)
        output_width = int(collage_width * scale)
        output_height = int(collage_height * scale)

        subprocess.run(
            [
                "convert",
                str(master_path),
                "-crop", f"{collage_width}x{collage_height}+0+0",  # Crop to actual collage
                "+repage",
                "-background", "white",  # White background for transparent areas
                "-alpha", "remove",      # Flatten transparency
                "-alpha", "off",         # Ensure no alpha channel in output
                "-resize", f"{output_width}x{output_height}",
                "-quality", "90",
                str(output_path)
            ],
            check=True
        )


def create_manifest(build_dir: Path, layout: Dict[str, Any], tiles: List[Path],
                   n_images: int) -> Dict[str, Any]:
    """
    Create manifest.json for the collage build.

    Args:
        build_dir: Build directory path
        layout: Layout configuration dict
        tiles: List of tile paths used
        n_images: Total images available

    Returns:
        Manifest dict
    """
    # Extract photo metadata
    photos = []
    for tile in tiles:
        email = extract_email_from_tile(tile)
        photos.append({
            "filename": tile.name,
            "email": email
        })

    manifest = {
        "created_at": int(datetime.now().timestamp()),
        "published_at": None,  # Set when published
        "algorithm": "montage-grid",
        "layout": {
            "cols": layout['cols'],
            "rows": layout['rows'],
            "cell_width": layout['cell_width'],
            "cell_height": layout['cell_height'],
            "collage_width": layout['collage_width'],
            "collage_height": layout['collage_height'],
            "strategy": layout['strategy'],
            "score": layout['total_score']
        },
        "photo_count": len(tiles),
        "total_available": n_images,
        "photos": photos,
        "permanent_url": None,  # Set when published
        "emails_sent": 0,
        "email_log": None
    }

    manifest_path = build_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


def build_collage(campaign_dir: Path, layout: Dict[str, Any], n_images: int,
                 build_id: Optional[str] = None, logger=None) -> Path:
    """
    Build a collage from tiles using the specified layout.

    Args:
        campaign_dir: Campaign directory (e.g., /tmp/collagen-local/test_prototype)
        layout: Layout configuration dict from grid_optimizer
        n_images: Number of images to include
        build_id: Optional build ID (default: timestamp)
        logger: Optional logger

    Returns:
        Path to build directory
    """
    if logger:
        logger.info(f"Building collage: {layout['cols']}×{layout['rows']}, {n_images} images")

    # Create build directory
    if not build_id:
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        build_id = f"{timestamp},{layout['used_images']}={layout['cols']}x{layout['rows']}"

    build_dir = campaign_dir / "collages" / build_id
    build_dir.mkdir(parents=True, exist_ok=True)

    renders_dir = build_dir / "renders"

    # Select tiles (oldest first)
    tiles_dir = campaign_dir / "tiles"
    tiles = get_tiles_oldest_first(tiles_dir, limit=n_images)

    if logger:
        logger.info(f"Selected {len(tiles)} tiles (oldest first)")

    # Check for email duplicates (warning only, per issue #8)
    duplicates = check_email_duplicates(tiles, logger=logger)

    # Generate render tiles
    if logger:
        logger.info(f"Generating render tiles: {layout['cell_width']}×{layout['cell_height']}px")

    generate_renders(tiles, renders_dir, layout['cell_width'], layout['cell_height'])

    # Generate montage
    png_4k_path = build_dir / "4096.png"

    if logger:
        logger.info(f"Generating montage: {layout['cols']}×{layout['rows']} grid")

    generate_montage(
        renders_dir, png_4k_path,
        layout['cols'], layout['rows'],
        layout['padding_h'], layout['padding_v'],
        layout['clip_h'], layout['clip_v'],
        4096  # Target size
    )

    # Generate derivatives
    if logger:
        logger.info("Generating JPEG derivatives (4096px, 1024px)")

    generate_derivatives(png_4k_path, build_dir, layout['collage_width'], layout['collage_height'])

    # Create manifest
    if logger:
        logger.info("Writing manifest.json")

    create_manifest(build_dir, layout, tiles, len(list(tiles_dir.glob("*.png"))))

    if logger:
        logger.info(f"✅ Collage built: {build_dir}")

    return build_dir
