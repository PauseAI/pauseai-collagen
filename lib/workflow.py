"""
Workflow orchestration for collage building.

Provides high-level functions that coordinate grid optimization, layout selection, and build.
Used by both CLI and webapp.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
from .grid_optimizer import get_top_layouts, evaluate_custom_grid
from .collage_generator import get_tiles_oldest_first


def get_layout_options(campaign_dir: Path, n_images: int) -> Dict[str, Any]:
    """
    Get layout options for building a collage.

    Args:
        campaign_dir: Campaign directory path
        n_images: Number of images to include

    Returns:
        Dict containing:
        - available_tiles: Number of tiles available
        - n_images: Number requested
        - top_layouts: List of top 3 recommended layouts
    """
    tiles_dir = campaign_dir / "tiles"
    available_tiles = len(list(tiles_dir.glob("*.png")))

    if n_images > available_tiles:
        raise ValueError(f"Requested {n_images} images but only {available_tiles} available")

    if available_tiles == 0:
        raise ValueError(f"No tiles found in {tiles_dir}")

    # Get top 3 layouts
    top_layouts = get_top_layouts(n_images, target_size=4096, top_n=3)

    if not top_layouts:
        raise ValueError(f"No valid layouts found for {n_images} images")

    return {
        "available_tiles": available_tiles,
        "n_images": n_images,
        "top_layouts": top_layouts
    }


def validate_custom_layout(cols: int, rows: int, n_images: int) -> Optional[Dict[str, Any]]:
    """
    Validate and evaluate a custom grid layout.

    Args:
        cols: Number of columns
        rows: Number of rows
        n_images: Total images available

    Returns:
        Layout dict if valid, None if invalid (clipping exceeds limits)
    """
    return evaluate_custom_grid(cols, rows, n_images, target_size=4096)


def preview_tiles_for_build(campaign_dir: Path, n_images: int) -> List[Dict[str, Any]]:
    """
    Get preview of which tiles will be used (oldest first).

    Args:
        campaign_dir: Campaign directory path
        n_images: Number of images to include

    Returns:
        List of tile info dicts with: path, name, mtime
    """
    tiles_dir = campaign_dir / "tiles"
    tiles = get_tiles_oldest_first(tiles_dir, limit=n_images)

    return [
        {
            "path": str(tile),
            "name": tile.name,
            "mtime": tile.stat().st_mtime
        }
        for tile in tiles
    ]
