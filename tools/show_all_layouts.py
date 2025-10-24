#!/usr/bin/env python3
"""
Show all scored layout options for a given number of images with score breakdown.

Usage:
    ./tools/show_all_layouts.py 277
    ./tools/show_all_layouts.py 281
"""

import sys
from pathlib import Path

# Add lib/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.grid_optimizer import optimize_for_n_images


def main():
    if len(sys.argv) != 2:
        print("Usage: ./tools/show_all_layouts.py <n_images>")
        print("Example: ./tools/show_all_layouts.py 277")
        sys.exit(1)

    n_images = int(sys.argv[1])

    print(f"\n{'='*80}")
    print(f"ALL LAYOUT OPTIONS FOR {n_images} IMAGES")
    print(f"{'='*80}\n")

    all_layouts = optimize_for_n_images(n_images, target_size=4096)
    all_layouts.sort(key=lambda c: c['total_score'])

    for i, layout in enumerate(all_layouts, 1):
        print(f"Option {i}:")
        print(f"  Grid: {layout['cols']}×{layout['rows']} ({layout['grid_slots']} slots)")
        print(f"  Used: {layout['used_images']} images")
        print(f"  Omitted: {layout['omitted_images']} ({layout['omit_fraction']*100:.1f}%)")
        print(f"  Cell: {layout['cell_width']}×{layout['cell_height']}px")
        print(f"  Collage: {layout['collage_width']}×{layout['collage_height']}px")
        print(f"  Strategy: {layout['strategy']}")

        # Show padding/clipping details
        if layout['padding_h'] > 0:
            print(f"  Padding H: {layout['padding_h']//2}px per edge")
        if layout['padding_v'] > 0:
            print(f"  Padding V: {layout['padding_v']//2}px per edge")
        if layout['clip_h'] > 0:
            print(f"  Clipping H: {layout['clip_h']//2}px per edge ({layout['clip_fraction_h']*100:.1f}% of cell)")
        if layout['clip_v'] > 0:
            print(f"  Clipping V: {layout['clip_v']//2}px per edge ({layout['clip_fraction_v']*100:.1f}% of cell)")

        # Score breakdown
        print(f"  Score breakdown:")
        print(f"    Omit cost:  {layout['omit_cost']:.1f}")
        print(f"    Fit cost:   {layout['fit_cost']:.1f}")
        print(f"    Total:      {layout['total_score']:.1f}")
        print()


    print(f"\nTotal layouts evaluated: {len(all_layouts)}")


if __name__ == "__main__":
    main()
