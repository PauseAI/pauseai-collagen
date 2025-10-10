#!/usr/bin/env python3
"""
Optimize grid layout for collage generation.

Explores ALL possible grid configurations (including using fewer than n images)
to build 4096x4096 collages from up to n images with 3:4 aspect ratio.

Cost model:
- Empty grid slots: Very bad (wasted space in grid)
- Omitted images: Proportional to k/n (fraction not used)
- Padding: Proportional to total padding pixels
- Clipping: Proportional to fraction of edge cells clipped
"""

from typing import List, Dict, Any, Tuple


def evaluate_fit_strategy(cols: int, rows: int, cell_width: float, cell_height: float,
                          collage_width: float, collage_height: float, target_size: int,
                          pad_cost: float = 1.0, clip_cost: float = 0.5) -> Tuple[str, float, Dict]:
    """
    Evaluate different strategies to fit collage into target square.

    Args:
        pad_cost: Cost per pixel of padding
        clip_cost: Cost per pixel of clipping (total pixels clipped across all edge cells)

    Returns:
        Tuple of (approach_name, total_cost, details_dict)
    """
    strategies = []

    # Strategy 1: Pad both (no scaling)
    padding_h = target_size - collage_width
    padding_v = target_size - collage_height

    strategies.append({
        'name': 'pad_both',
        'padding_h': padding_h,
        'padding_v': padding_v,
        'clip_fraction_h': 0.0,
        'clip_fraction_v': 0.0,
        'clip_pixels_total': 0,
        'cost': (padding_h + padding_v) * pad_cost
    })

    # Strategy 2: Scale to fill width exactly
    scale_w = target_size / collage_width
    new_height = collage_height * scale_w
    scaled_cell_height = cell_height * scale_w

    if new_height > target_size:
        # Clip top and bottom
        clip_total_v = new_height - target_size
        clip_per_edge_v = clip_total_v / 2  # Split between top and bottom
        clip_fraction_v = clip_per_edge_v / scaled_cell_height  # Fraction of each edge cell

        # Total pixels clipped: clip amount per cell × number of cells on each edge
        clip_pixels_per_cell = clip_per_edge_v
        clip_pixels_total = clip_pixels_per_cell * cols * 2  # cols cells on top, cols on bottom

        strategies.append({
            'name': 'fill_w_clip_v',
            'padding_h': 0,
            'padding_v': 0,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': clip_fraction_v,
            'clip_pixels_total': clip_pixels_total,
            'cost': clip_pixels_total * clip_cost
        })
    else:
        # Pad vertical
        strategies.append({
            'name': 'fill_w_pad_v',
            'padding_h': 0,
            'padding_v': target_size - new_height,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': 0,
            'cost': (target_size - new_height) * pad_cost
        })

    # Strategy 3: Scale to fill height exactly
    scale_h = target_size / collage_height
    new_width = collage_width * scale_h
    scaled_cell_width = cell_width * scale_h

    if new_width > target_size:
        # Clip left and right
        clip_total_h = new_width - target_size
        clip_per_edge_h = clip_total_h / 2  # Split between left and right
        clip_fraction_h = clip_per_edge_h / scaled_cell_width  # Fraction of each edge cell

        # Total pixels clipped: clip amount per cell × number of cells on each edge
        clip_pixels_per_cell = clip_per_edge_h
        clip_pixels_total = clip_pixels_per_cell * rows * 2  # rows cells on left, rows on right

        strategies.append({
            'name': 'fill_h_clip_w',
            'padding_h': 0,
            'padding_v': 0,
            'clip_fraction_h': clip_fraction_h,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': clip_pixels_total,
            'cost': clip_pixels_total * clip_cost
        })
    else:
        # Pad horizontal
        strategies.append({
            'name': 'fill_h_pad_w',
            'padding_h': target_size - new_width,
            'padding_v': 0,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': 0,
            'cost': (target_size - new_width) * pad_cost
        })

    # Find best strategy
    best = min(strategies, key=lambda s: s['cost'])
    return (best['name'], best['cost'], best)


def explore_grid_configs(n_images: int, target_size: int = 4096, max_search: int = 80) -> List[Dict[str, Any]]:
    """
    Explore ALL possible grid configurations for up to n images.

    Args:
        n_images: Maximum number of images available
        target_size: Target collage size (square, e.g., 4096)
        max_search: Maximum cols/rows to search

    Returns:
        List of grid configurations with scores
    """
    configs = []

    # Cost weights (tunable)
    EMPTY_SLOT_COST = 100000   # Empty grid slots: very bad (wasted grid space)
    OMIT_BASE_COST = 1500      # Base cost for omitting images (multiplied by fraction omitted)
    PAD_COST = 1.0             # Cost per pixel of padding
    CLIP_COST = 0.5            # Cost per pixel of clipping (applied to total clipped pixels across all edge cells)

    # Try all reasonable grid sizes
    for cols in range(1, max_search + 1):
        for rows in range(1, max_search + 1):
            total_slots = cols * rows

            # How many images actually used?
            used_images = min(n_images, total_slots)
            empty_slots = total_slots - used_images
            omitted_images = n_images - used_images

            # Each cell is 3:4 aspect ratio (portrait: width:height = 3:4)
            # cell_height = cell_width * 4/3

            # Maximum cell_width constrained by both dimensions
            max_cell_width_by_width = target_size / cols
            max_cell_width_by_height = target_size / (rows * 4/3)

            cell_width = min(max_cell_width_by_width, max_cell_width_by_height)
            cell_height = cell_width * 4 / 3

            # Actual collage dimensions (before fitting to target)
            collage_width = cols * cell_width
            collage_height = rows * cell_height

            # Evaluate fit strategies
            approach, fit_cost, fit_details = evaluate_fit_strategy(
                cols, rows, cell_width, cell_height,
                collage_width, collage_height, target_size, PAD_COST, CLIP_COST
            )

            # Calculate omitted image cost as fraction of total
            omit_fraction = omitted_images / n_images if n_images > 0 else 0
            omit_cost = OMIT_BASE_COST * omit_fraction

            # Total score (lower is better)
            total_score = (empty_slots * EMPTY_SLOT_COST +
                          omit_cost +
                          fit_cost)

            configs.append({
                'cols': cols,
                'rows': rows,
                'total_slots': total_slots,
                'used_images': used_images,
                'empty_slots': empty_slots,
                'omitted_images': omitted_images,
                'omit_fraction': omit_fraction,
                'cell_width': cell_width,
                'cell_height': cell_height,
                'cell_pixels': cell_width * cell_height,
                'collage_width': collage_width,
                'collage_height': collage_height,
                'approach': approach,
                'padding_h': fit_details.get('padding_h', 0),
                'padding_v': fit_details.get('padding_v', 0),
                'clip_fraction_h': fit_details.get('clip_fraction_h', 0),
                'clip_fraction_v': fit_details.get('clip_fraction_v', 0),
                'clip_pixels_total': fit_details.get('clip_pixels_total', 0),
                'total_score': total_score,
                'empty_cost': empty_slots * EMPTY_SLOT_COST,
                'omit_cost': omit_cost,
                'fit_cost': fit_cost
            })

    return configs


def main():
    """Run optimization for different image counts."""
    test_counts = [229, 500, 1000, 5000]

    for n in test_counts:
        print("=" * 140)
        print(f"OPTIMIZING GRID FOR UP TO {n} IMAGES (target: 4096×4096, 3:4 portrait cells)")
        print("=" * 140)

        configs = explore_grid_configs(n, target_size=4096)

        # Sort by score (best first)
        configs.sort(key=lambda c: c['total_score'])

        # Show top 20 options with detailed cost breakdown
        print(f"\nTop 20 configurations (out of {len(configs)} evaluated):")
        print("-" * 150)
        print(f"{'Grid':<8} {'Used/n':<10} {'Cell Size':<12} {'Pad(h,v)':<14} {'Clip%(h,v)':<14} "
              f"{'EmptyCost':<11} {'OmitCost':<10} {'FitCost':<10} {'Total':<10}")
        print("-" * 150)

        for cfg in configs[:20]:
            grid = f"{cfg['cols']}×{cfg['rows']}"
            used_str = f"{cfg['used_images']}/{n}"
            cell_size = f"{cfg['cell_width']:.0f}×{cfg['cell_height']:.0f}"

            pad_str = f"{cfg['padding_h']:.0f},{cfg['padding_v']:.0f}" if cfg['padding_h'] or cfg['padding_v'] else "-"

            clip_str = ""
            if cfg['clip_fraction_h'] > 0 and cfg['clip_fraction_v'] > 0:
                clip_str = f"{100*cfg['clip_fraction_h']:.1f},{100*cfg['clip_fraction_v']:.1f}"
            elif cfg['clip_fraction_h'] > 0:
                clip_str = f"{100*cfg['clip_fraction_h']:.1f}h"
            elif cfg['clip_fraction_v'] > 0:
                clip_str = f"{100*cfg['clip_fraction_v']:.1f}v"
            else:
                clip_str = "-"

            print(f"{grid:<8} {used_str:<10} {cell_size:<12} {pad_str:<14} {clip_str:<14} "
                  f"{cfg['empty_cost']:<11.0f} {cfg['omit_cost']:<10.1f} {cfg['fit_cost']:<10.1f} {cfg['total_score']:<10.0f}")

        # Show winner details
        best = configs[0]
        print(f"\n{'=' * 140}")
        print(f"RECOMMENDED: {best['cols']}×{best['rows']} grid using {best['used_images']}/{n} images")
        print(f"{'=' * 140}")
        print(f"  Cell size: {best['cell_width']:.1f}×{best['cell_height']:.1f} pixels")
        print(f"  Images omitted: {best['omitted_images']} ({100 * best['omit_fraction']:.1f}%)")
        print(f"  Empty grid slots: {best['empty_slots']}")
        print(f"  Approach: {best['approach']}")

        if best['padding_h'] > 0 or best['padding_v'] > 0:
            print(f"  Padding: {best['padding_h']:.0f}px horizontal, {best['padding_v']:.0f}px vertical")

        if best['clip_fraction_h'] > 0:
            print(f"  Left/right edge cells: {100*best['clip_fraction_h']:.1f}% of width clipped")
            print(f"    (Affects {best['rows']} cells per edge, {best['clip_pixels_total']:.0f} total pixels clipped)")

        if best['clip_fraction_v'] > 0:
            print(f"  Top/bottom edge cells: {100*best['clip_fraction_v']:.1f}% of height clipped")
            print(f"    (Affects {best['cols']} cells per edge, {best['clip_pixels_total']:.0f} total pixels clipped)")

        print(f"\n  Cost breakdown:")
        print(f"    Empty slots: {best['empty_cost']:.1f} ({best['empty_slots']} × 100,000)")
        print(f"    Omitted: {best['omit_cost']:.1f} ({best['omitted_images']}/{n} = {best['omit_fraction']:.4f} × 1,500)")
        print(f"    Fit: {best['fit_cost']:.1f}", end="")
        if best['padding_h'] or best['padding_v']:
            print(f" ({best['padding_h'] + best['padding_v']:.0f} pad pixels × 1.0)")
        elif best['clip_pixels_total'] > 0:
            print(f" ({best['clip_pixels_total']:.0f} clip pixels × 0.5)")
        else:
            print(f" (perfect fit)")
        print(f"    TOTAL: {best['total_score']:.1f}")

        print(f"\n  Memory estimate: ~{best['used_images'] * best['cell_pixels'] * 3 / 1024 / 1024:.0f}MB uncompressed")

        # Also show best non-perfect fit for comparison
        non_perfect = [c for c in configs if c['padding_h'] > 0 or c['padding_v'] > 0 or c['clip_pixels_total'] > 0]
        if non_perfect and non_perfect[0]['total_score'] != best['total_score']:
            print(f"\n  Best non-perfect alternative: {non_perfect[0]['cols']}×{non_perfect[0]['rows']} "
                  f"(uses {non_perfect[0]['used_images']}/{n}, score: {non_perfect[0]['total_score']:.1f})")

        print()


if __name__ == '__main__':
    main()
