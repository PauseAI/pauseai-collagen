#!/usr/bin/env python3
"""
Interactive collage builder CLI.

Selects tiles (oldest first), calculates layout options, lets user choose, and builds collage.

Usage:
    ./tools/build_collage.py test_prototype 20    # Build with 20 images
    ./tools/build_collage.py sayno 238             # Build with all sayno images
"""

import sys
import logging
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.workflow import get_layout_options, validate_custom_layout
from lib.grid_optimizer import format_layout_description
from lib.collage_generator import build_collage


# Configuration
LOCAL_BASE = Path("/tmp/collagen-local")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def prompt_layout_selection(options: dict) -> dict:
    """
    CLI prompt for layout selection.

    Args:
        options: Dict from get_layout_options()

    Returns:
        Selected layout configuration dict
    """
    n_images = options['n_images']
    top_layouts = options['top_layouts']

    print()
    print("=" * 80)
    print(f"LAYOUT OPTIONS FOR {n_images} IMAGES")
    print("=" * 80)
    print()
    print("Top 3 recommended layouts:")
    print()

    for i, layout in enumerate(top_layouts, 1):
        print(f"Option {i}:")
        print(format_layout_description(layout))
        print()

    print("Option 4: Custom grid (specify cols×rows)")
    print()

    # Get user choice
    while True:
        choice = input("Select layout (1-4): ").strip()

        if choice in ['1', '2', '3']:
            idx = int(choice) - 1
            selected = top_layouts[idx]
            print()
            print(f"✓ Selected: {selected['cols']}×{selected['rows']} grid")
            return selected

        elif choice == '4':
            # Custom grid
            custom_input = input("Enter custom grid (e.g., 15x20): ").strip()

            try:
                cols, rows = custom_input.lower().split('x')
                cols = int(cols)
                rows = int(rows)

                print()
                print(f"Evaluating custom grid: {cols}×{rows}...")

                custom_layout = validate_custom_layout(cols, rows, n_images)

                if not custom_layout:
                    print("❌ This grid doesn't work (clipping exceeds limits)")
                    print("   Try a different size or use one of the recommended options.")
                    print()
                    continue

                print()
                print(format_layout_description(custom_layout))
                print()

                confirm = input("Use this layout? (y/n): ").strip().lower()
                if confirm == 'y':
                    print()
                    print(f"✓ Selected: {custom_layout['cols']}×{custom_layout['rows']} grid")
                    return custom_layout
                else:
                    print()
                    continue

            except (ValueError, AttributeError):
                print("Invalid format. Use: COLSxROWS (e.g., 15x20)")
                print()
                continue

        else:
            print("Invalid choice. Enter 1, 2, 3, or 4.")
            print()


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: ./tools/build_collage.py <campaign> [n_images]")
        print("Example: ./tools/build_collage.py test_prototype      # Use all tiles")
        print("Example: ./tools/build_collage.py test_prototype 20   # Use 20 oldest tiles")
        sys.exit(1)

    campaign = sys.argv[1]

    campaign_dir = LOCAL_BASE / campaign

    if not campaign_dir.exists():
        print(f"❌ Campaign directory not found: {campaign_dir}")
        print(f"   Run ./tools/sync_tiles_from_ec2.py {campaign} first")
        sys.exit(1)

    # Default to all available tiles if not specified
    tiles_dir = campaign_dir / "tiles"
    available_tiles = len(list(tiles_dir.glob("*.png")))

    if available_tiles == 0:
        print(f"❌ No tiles found in {tiles_dir}")
        sys.exit(1)

    if len(sys.argv) == 3:
        n_images = int(sys.argv[2])
        if n_images > available_tiles:
            print(f"❌ Requested {n_images} images but only {available_tiles} available")
            sys.exit(1)
    else:
        n_images = available_tiles

    print(f"Campaign: {campaign}")
    print(f"Available tiles: {available_tiles}")
    print(f"Building with: {n_images} images (oldest first)")

    # Get layout options
    try:
        options = get_layout_options(campaign_dir, n_images)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Prompt for layout
    layout = prompt_layout_selection(options)

    # Build collage
    print()
    print("=" * 80)
    print("BUILDING COLLAGE")
    print("=" * 80)
    print()

    build_dir = build_collage(campaign_dir, layout, n_images, logger=logger)

    print()
    print("=" * 80)
    print("✅ BUILD COMPLETE")
    print("=" * 80)
    print()
    print(f"Build directory: {build_dir}")
    print(f"  4096.png:      {build_dir / '4096.png'}")
    print(f"  4096.jpg:      {build_dir / '4096.jpg'}")
    print(f"  1024.jpg:      {build_dir / '1024.jpg'}")
    print(f"  manifest.json: {build_dir / 'manifest.json'}")
    print()


if __name__ == "__main__":
    main()
