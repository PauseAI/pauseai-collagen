#!/usr/bin/env python3
"""
Optimize grid layout for collage generation (v2).

Smart search:
1. Explores using fewer images (k from n down)
2. Finds factorizations where cols/rows ≈ 4/3 (for square output from 3:4 cells)
3. Tests multiple cell sizing strategies (padding, clip one axis, clip both)
"""

from typing import List, Dict, Any, Tuple
import math


def find_factorizations(k: int, target_ratio: float = 4/3, max_candidates: int = 10) -> List[Tuple[int, int]]:
    """
    Find factorizations of k where cols/rows ≈ target_ratio.

    Args:
        k: Number to factorize
        target_ratio: Target cols/rows ratio (4/3 for 3:4 portrait cells → square output)
        max_candidates: Maximum number of factorizations to return

    Returns:
        List of (cols, rows) tuples, sorted by proximity to target_ratio
    """
    factorizations = []

    for rows in range(1, int(math.sqrt(k)) + 1):
        if k % rows == 0:
            cols = k // rows
            ratio = cols / rows
            ratio_error = abs(ratio - target_ratio)

            factorizations.append({
                'cols': cols,
                'rows': rows,
                'ratio': ratio,
                'ratio_error': ratio_error
            })

    # Sort by proximity to target ratio
    factorizations.sort(key=lambda f: f['ratio_error'])

    return [(f['cols'], f['rows']) for f in factorizations[:max_candidates]]


def evaluate_cell_sizing(cols: int, rows: int, target_size: int, pad_cost: float = 1.0,
                        clip_cost: float = 0.5) -> List[Dict[str, Any]]:
    """
    Evaluate different cell sizing strategies for a given grid.

    Three strategies:
    1. Small cells: Fit within target (requires padding)
    2. Medium cells: Fill one dimension exactly (clip other)
    3. Large cells: Overflow both dimensions (clip both edges)

    Returns:
        List of configuration dicts with costs
    """
    configs = []

    # Cell aspect ratio: 3:4 (portrait)
    aspect_ratio = 3 / 4

    # Strategy 1: Small cells (fit within both dimensions)
    max_cell_width_by_width = target_size / cols
    max_cell_width_by_height = target_size / (rows * (4/3))

    cell_width_small = min(max_cell_width_by_width, max_cell_width_by_height)
    cell_height_small = cell_width_small * 4 / 3

    collage_width = cols * cell_width_small
    collage_height = rows * cell_height_small

    padding_h = target_size - collage_width
    padding_v = target_size - collage_height

    configs.append({
        'strategy': 'small_cells_pad',
        'cell_width': cell_width_small,
        'cell_height': cell_height_small,
        'collage_width': collage_width,
        'collage_height': collage_height,
        'padding_h': padding_h,
        'padding_v': padding_v,
        'clip_fraction_h': 0.0,
        'clip_fraction_v': 0.0,
        'clip_pixels_total': 0,
        'cost': (padding_h + padding_v) * pad_cost
    })

    # Strategy 2a: Medium cells (fill width, clip/pad height)
    cell_width_fill_w = target_size / cols
    cell_height_fill_w = cell_width_fill_w * 4 / 3
    collage_height_fill_w = rows * cell_height_fill_w

    if collage_height_fill_w > target_size:
        # Clip vertical
        clip_total_v = collage_height_fill_w - target_size
        clip_per_edge_v = clip_total_v / 2
        clip_fraction_v = clip_per_edge_v / cell_height_fill_w
        clip_pixels_total = clip_per_edge_v * cols * 2

        configs.append({
            'strategy': 'fill_w_clip_v',
            'cell_width': cell_width_fill_w,
            'cell_height': cell_height_fill_w,
            'collage_width': target_size,
            'collage_height': collage_height_fill_w,
            'padding_h': 0,
            'padding_v': 0,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': clip_fraction_v,
            'clip_pixels_total': clip_pixels_total,
            'cost': clip_pixels_total * clip_cost
        })
    else:
        # Pad vertical
        pad_v = target_size - collage_height_fill_w
        configs.append({
            'strategy': 'fill_w_pad_v',
            'cell_width': cell_width_fill_w,
            'cell_height': cell_height_fill_w,
            'collage_width': target_size,
            'collage_height': collage_height_fill_w,
            'padding_h': 0,
            'padding_v': pad_v,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': 0,
            'cost': pad_v * pad_cost
        })

    # Strategy 2b: Medium cells (fill height, clip/pad width)
    cell_height_fill_h = target_size / rows / (4/3)
    cell_width_fill_h = cell_height_fill_h * 3 / 4
    collage_width_fill_h = cols * cell_width_fill_h

    if collage_width_fill_h > target_size:
        # Clip horizontal
        clip_total_h = collage_width_fill_h - target_size
        clip_per_edge_h = clip_total_h / 2
        clip_fraction_h = clip_per_edge_h / cell_width_fill_h
        clip_pixels_total = clip_per_edge_h * rows * 2

        configs.append({
            'strategy': 'fill_h_clip_w',
            'cell_width': cell_width_fill_h,
            'cell_height': cell_height_fill_h,
            'collage_width': collage_width_fill_h,
            'collage_height': target_size,
            'padding_h': 0,
            'padding_v': 0,
            'clip_fraction_h': clip_fraction_h,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': clip_pixels_total,
            'cost': clip_pixels_total * clip_cost
        })
    else:
        # Pad horizontal
        pad_h = target_size - collage_width_fill_h
        configs.append({
            'strategy': 'fill_h_pad_w',
            'cell_width': cell_width_fill_h,
            'cell_height': cell_height_fill_h,
            'collage_width': collage_width_fill_h,
            'collage_height': target_size,
            'padding_h': pad_h,
            'padding_v': 0,
            'clip_fraction_h': 0.0,
            'clip_fraction_v': 0.0,
            'clip_pixels_total': 0,
            'cost': pad_h * pad_cost
        })

    # Strategy 3: Large cells (overflow both dimensions, clip both)
    # Make cells slightly larger to fill target better
    cell_width_large = max(max_cell_width_by_width, max_cell_width_by_height)
    cell_height_large = cell_width_large * 4 / 3

    collage_width_large = cols * cell_width_large
    collage_height_large = rows * cell_height_large

    # Scale to fit in target
    scale_to_fit = min(target_size / collage_width_large, target_size / collage_height_large)

    # After scaling, one dimension fills exactly, other might clip
    scaled_width = collage_width_large * scale_to_fit
    scaled_height = collage_height_large * scale_to_fit

    clip_h = max(0, scaled_width - target_size)
    clip_v = max(0, scaled_height - target_size)

    # If this actually clips (not same as medium strategy)
    if clip_h > 0 and clip_v > 0:
        clip_pixels_total = clip_h + clip_v  # Simplified
        configs.append({
            'strategy': 'large_cells_clip_both',
            'cell_width': cell_width_large,
            'cell_height': cell_height_large,
            'collage_width': collage_width_large,
            'collage_height': collage_height_large,
            'padding_h': 0,
            'padding_v': 0,
            'clip_fraction_h': clip_h / (cell_width_large * scale_to_fit),
            'clip_fraction_v': clip_v / (cell_height_large * scale_to_fit),
            'clip_pixels_total': clip_pixels_total,
            'cost': clip_pixels_total * clip_cost
        })

    return configs


def optimize_for_n_images(n_images: int, target_size: int = 4096,
                         empty_cost: float = 100000, omit_base_cost: float = 1500,
                         pad_cost: float = 1.0, clip_cost: float = 0.5) -> List[Dict[str, Any]]:
    """
    Smart search: explore using k <= n images with good factorizations.

    Args:
        n_images: Maximum images available

    Returns:
        List of all viable configurations
    """
    all_configs = []

    # Try k from n down to 1
    # Stop early if omission cost alone exceeds best known total
    best_score_so_far = float('inf')

    for k in range(n_images, 0, -1):
        # Calculate omission cost for using k images
        omitted = n_images - k
        omit_fraction = omitted / n_images
        omit_cost = omit_base_cost * omit_fraction

        # Early termination: if omission cost alone > best total, stop
        if omit_cost > best_score_so_far:
            break

        # Find good factorizations of k (cols/rows ≈ 4/3 for square output)
        factorizations = find_factorizations(k, target_ratio=4/3, max_candidates=5)

        for cols, rows in factorizations:
            # Evaluate different cell sizing strategies
            sizing_configs = evaluate_cell_sizing(cols, rows, target_size, pad_cost, clip_cost)

            for cfg in sizing_configs:
                total_score = omit_cost + cfg['cost']

                # Update best score
                if total_score < best_score_so_far:
                    best_score_so_far = total_score

                all_configs.append({
                    'k': k,
                    'cols': cols,
                    'rows': rows,
                    'used_images': k,
                    'omitted_images': omitted,
                    'omit_fraction': omit_fraction,
                    **cfg,
                    'omit_cost': omit_cost,
                    'total_score': total_score
                })

    return all_configs


def main():
    """Run optimization."""
    n = 229

    print("=" * 140)
    print(f"SMART GRID OPTIMIZATION FOR {n} IMAGES (target: 4096×4096, 3:4 portrait cells)")
    print("=" * 140)
    print("\nCost weights:")
    print("  Empty slots: 100,000 per slot (very bad)")
    print("  Omitted images: 1,500 × (k/n) where k images omitted")
    print("  Padding: 1.0 per pixel")
    print("  Clipping: 0.5 per pixel")
    print()

    configs = optimize_for_n_images(n, target_size=4096)

    print(f"Evaluated {len(configs)} configurations")

    # Sort by score
    configs.sort(key=lambda c: c['total_score'])

    # Show top 30
    print(f"\nTop 30 configurations:")
    print("-" * 140)
    print(f"{'Grid':<8} {'k/n':<10} {'Cell Size':<12} {'Pad(h,v)':<14} {'Clip%(h,v)':<16} "
          f"{'OmitCost':<10} {'FitCost':<10} {'Total':<10}")
    print("-" * 140)

    for cfg in configs[:30]:
        grid = f"{cfg['cols']}×{cfg['rows']}"
        used_str = f"{cfg['used_images']}/{n}"
        cell_size = f"{cfg['cell_width']:.0f}×{cfg['cell_height']:.0f}"

        pad_str = f"{cfg['padding_h']:.0f},{cfg['padding_v']:.0f}" if cfg['padding_h'] or cfg['padding_v'] else "-"

        clip_str = ""
        if cfg['clip_fraction_h'] > 0 and cfg['clip_fraction_v'] > 0:
            clip_str = f"{100*cfg['clip_fraction_h']:.1f}h,{100*cfg['clip_fraction_v']:.1f}v"
        elif cfg['clip_fraction_h'] > 0:
            clip_str = f"{100*cfg['clip_fraction_h']:.1f}h"
        elif cfg['clip_fraction_v'] > 0:
            clip_str = f"{100*cfg['clip_fraction_v']:.1f}v"
        else:
            clip_str = "-"

        print(f"{grid:<8} {used_str:<10} {cell_size:<12} {pad_str:<14} {clip_str:<16} "
              f"{cfg['omit_cost']:<10.1f} {cfg['cost']:<10.1f} {cfg['total_score']:<10.0f}")

    # Show winner details
    best = configs[0]
    print(f"\n{'=' * 140}")
    print(f"WINNER: {best['cols']}×{best['rows']} grid using {best['used_images']}/{n} images")
    print(f"{'=' * 140}")
    print(f"  Strategy: {best['strategy']}")
    print(f"  Cell size: {best['cell_width']:.1f}×{best['cell_height']:.1f} pixels")
    print(f"  Collage size (before fit): {best['collage_width']:.0f}×{best['collage_height']:.0f}")
    print(f"  Images omitted: {best['omitted_images']} ({100*best['omit_fraction']:.1f}%)")

    if best['padding_h'] or best['padding_v']:
        print(f"  Padding: {best['padding_h']:.0f}px horizontal, {best['padding_v']:.0f}px vertical")

    if best['clip_fraction_h'] > 0:
        print(f"  Horizontal clipping: {100*best['clip_fraction_h']:.1f}% of edge cells ({best['rows']} cells per edge)")

    if best['clip_fraction_v'] > 0:
        print(f"  Vertical clipping: {100*best['clip_fraction_v']:.1f}% of edge cells ({best['cols']} cells per edge)")

    print(f"\n  Cost breakdown:")
    print(f"    Omitted images: {best['omit_cost']:.1f} ({best['omitted_images']}/{n} = {best['omit_fraction']:.4f} × 1,500)")
    print(f"    Fit: {best['cost']:.1f}", end="")
    if best['padding_h'] or best['padding_v']:
        print(f" ({best['padding_h'] + best['padding_v']:.0f} padding pixels × 1.0)")
    elif best['clip_pixels_total'] > 0:
        print(f" ({best['clip_pixels_total']:.0f} clipping pixels × 0.5)")
    else:
        print(" (perfect fit)")
    print(f"    TOTAL: {best['total_score']:.1f}")

    print(f"\n  Memory: ~{best['used_images'] * best['cell_width'] * best['cell_height'] * 3 / 1024 / 1024:.0f}MB uncompressed")


if __name__ == '__main__':
    main()
