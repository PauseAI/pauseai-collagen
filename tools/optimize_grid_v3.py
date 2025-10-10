#!/usr/bin/env python3
"""
Optimize grid layout for collage generation (v3).

Smart search with exact 3:4 cells:
1. Only uses (3k)×(4k) cell sizes for integer k
2. For each grid, explores k from "largest that pads both" to "smallest that clips both"
3. Shows full trade-off spectrum
"""

from typing import List, Dict, Any, Tuple
import math

# Cost weights (tune here - single source of truth)
EMPTY_SLOT_COST = 100000   # Empty grid slots: very bad (wasted grid space)
OMIT_BASE_COST = 1500      # Base cost for omitting images (multiplied by fraction omitted)
PAD_COST = 1.0             # Cost per pixel of padding
CLIP_COST = 2.0            # Cost per pixel of clipping
MAX_CLIP_FRACTION = 0.33   # Don't try cells that clip > 33% of edge


def find_factorizations(k: int, target_ratio: float = 4/3, max_candidates: int = 8,
                       min_ratio: float = 0.5, max_ratio: float = 2.0) -> List[Tuple[int, int]]:
    """
    Find factorizations of k where cols/rows ≈ target_ratio.

    For 3:4 portrait cells in square output, target_ratio = 4/3.

    Args:
        min_ratio: Minimum cols/rows ratio to consider (e.g., 0.5 = 1:2, very tall)
        max_ratio: Maximum cols/rows ratio to consider (e.g., 2.0 = 2:1, very wide)
    """
    factorizations = []

    for rows in range(1, int(math.sqrt(k)) + 1):
        if k % rows == 0:
            cols = k // rows
            ratio = cols / rows

            # Filter by ratio range
            if ratio < min_ratio or ratio > max_ratio:
                continue

            ratio_error = abs(ratio - target_ratio)

            factorizations.append({
                'cols': cols,
                'rows': rows,
                'ratio': ratio,
                'ratio_error': ratio_error
            })

    factorizations.sort(key=lambda f: f['ratio_error'])
    return [(f['cols'], f['rows']) for f in factorizations[:max_candidates]]


def evaluate_grid_with_k(cols: int, rows: int, k: int, target_size: int) -> Dict[str, Any]:
    """
    Evaluate a specific grid with cell size (3k)×(4k).

    Uses module-level constants: PAD_COST, CLIP_COST, MAX_CLIP_FRACTION

    Returns:
        Configuration dict with costs, or None if clipping exceeds limit
    """
    # Exact 3:4 cell dimensions
    cell_width = 3 * k
    cell_height = 4 * k

    # Collage dimensions (no scaling)
    collage_width = cols * cell_width
    collage_height = rows * cell_height

    # Determine padding/clipping needed
    padding_h = max(0, target_size - collage_width)
    padding_v = max(0, target_size - collage_height)

    clip_h = max(0, collage_width - target_size)
    clip_v = max(0, collage_height - target_size)

    # Calculate clipping as fraction of edge cells
    clip_fraction_h = (clip_h / 2 / cell_width) if clip_h > 0 else 0.0
    clip_fraction_v = (clip_v / 2 / cell_height) if clip_v > 0 else 0.0

    # Skip if clipping exceeds limit
    if clip_fraction_h > MAX_CLIP_FRACTION or clip_fraction_v > MAX_CLIP_FRACTION:
        return None

    # Determine strategy
    if clip_h > 0 and clip_v > 0:
        strategy = 'clip_both'
    elif clip_h > 0:
        strategy = 'clip_h_pad_v'
    elif clip_v > 0:
        strategy = 'clip_v_pad_h'
    else:
        strategy = 'pad_both'

    # Calculate fit cost
    fit_cost = (padding_h + padding_v) * PAD_COST + (clip_h + clip_v) * CLIP_COST

    return {
        'k': k,
        'strategy': strategy,
        'cell_width': cell_width,
        'cell_height': cell_height,
        'collage_width': collage_width,
        'collage_height': collage_height,
        'padding_h': padding_h,
        'padding_v': padding_v,
        'clip_h': clip_h,
        'clip_v': clip_v,
        'clip_fraction_h': clip_fraction_h,
        'clip_fraction_v': clip_fraction_v,
        'fit_cost': fit_cost
    }


def explore_grid_k_range(cols: int, rows: int, target_size: int) -> List[Dict[str, Any]]:
    """
    For a given grid, find range of k from "pads both" to "clips both".

    Returns:
        List of configurations for different k values
    """
    configs = []

    # Find k range
    k_width_exact = target_size / (cols * 3)
    k_height_exact = target_size / (rows * 4)

    k_min = int(min(k_width_exact, k_height_exact)) - 2
    k_max = int(max(k_width_exact, k_height_exact)) + 2

    k_min = max(1, k_min)

    for k in range(k_min, k_max + 1):
        cfg = evaluate_grid_with_k(cols, rows, k, target_size)
        if cfg is not None:  # Skip if clipping exceeded MAX_CLIP_FRACTION
            configs.append(cfg)

    # Find useful range: from largest k with pad_both to smallest k with clip_both
    # Don't keep smaller k values that just add more padding (worse than larger cells)
    pad_both_configs = [c for c in configs if c['strategy'] == 'pad_both']
    clip_both_configs = [c for c in configs if c['strategy'] == 'clip_both']

    if pad_both_configs:
        # Keep only the largest k that pads both (best cell size with padding)
        largest_pad_both_k = max(c['k'] for c in pad_both_configs)
        # Keep all k >= this value (mixed strategies and clip_both)
        return [c for c in configs if c['k'] >= largest_pad_both_k]
    else:
        # No pad_both, keep all (all are clipping variants)
        return configs


def optimize_for_n_images(n_images: int, target_size: int = 4096) -> List[Dict[str, Any]]:
    """
    Smart search: explore using k <= n images with good factorizations.

    Uses module-level constants: OMIT_BASE_COST
    """
    all_configs = []

    best_score_so_far = float('inf')

    for k in range(n_images, 0, -1):
        omitted = n_images - k
        omit_fraction = omitted / n_images
        omit_cost = OMIT_BASE_COST * omit_fraction

        if omit_cost > best_score_so_far:
            break

        factorizations = find_factorizations(k, target_ratio=4/3, max_candidates=5)

        for cols, rows in factorizations:
            k_configs = explore_grid_k_range(cols, rows, target_size)

            for cfg in k_configs:
                total_score = omit_cost + cfg['fit_cost']

                if total_score < best_score_so_far:
                    best_score_so_far = total_score

                all_configs.append({
                    'cols': cols,
                    'rows': rows,
                    'grid_slots': cols * rows,
                    'used_images': k,
                    'omitted_images': omitted,
                    'omit_fraction': omit_fraction,
                    'omit_cost': omit_cost,
                    'total_score': total_score,
                    **cfg
                })

    return all_configs


def format_edge_adjustment(padding_h, padding_v, clip_h, clip_v):
    """Format edge adjustments as (+pad/-clip per edge)."""
    h_val = padding_h / 2 if padding_h > 0 else -(clip_h / 2)
    v_val = padding_v / 2 if padding_v > 0 else -(clip_v / 2)

    h_str = f"{h_val:+.0f}" if h_val != 0 else "0"
    v_str = f"{v_val:+.0f}" if v_val != 0 else "0"

    return f"{h_str},{v_str}"


def format_cost_calculation(omit_fraction, padding_h, padding_v, clip_h, clip_v, total):
    """Format the arithmetic cost calculation using module-level constants."""
    parts = []
    parts.append(f"{OMIT_BASE_COST:.0f}×{omit_fraction:.4f}")

    if padding_h or padding_v:
        parts.append(f"{PAD_COST:.1f}×{padding_h + padding_v:.0f}")

    if clip_h or clip_v:
        parts.append(f"{CLIP_COST:.1f}×{clip_h + clip_v:.0f}")

    return " + ".join(parts) + f" = {total:.1f}"


def main():
    """Run optimization."""
    n = 229

    print("=" * 160)
    print(f"GRID OPTIMIZATION FOR {n} IMAGES (target: 4096×4096, exact 3:4 cells)")
    print("=" * 160)
    print("\nCost weights:")
    print(f"  Omitted images: {OMIT_BASE_COST} × (omitted/n)")
    print(f"  Padding: {PAD_COST} per pixel")
    print(f"  Clipping: {CLIP_COST} per pixel")
    print(f"  Max clip fraction: {MAX_CLIP_FRACTION*100:.0f}%")
    print()

    configs = optimize_for_n_images(n, target_size=4096)

    print(f"Evaluated {len(configs)} configurations\n")

    # Sort by: (1) omitted images, (2) cell size
    configs.sort(key=lambda c: (c['omitted_images'], -c['cell_width']))

    # Write full report to file
    with open('grid_optimization_report.txt', 'w') as f:
        f.write("=" * 160 + "\n")
        f.write(f"FULL GRID OPTIMIZATION REPORT FOR {n} IMAGES\n")
        f.write("=" * 160 + "\n\n")
        f.write("Sorted by: (1) images omitted, (2) cell size (descending)\n")
        f.write("Edge adjustments: +padding or -clipping per edge\n\n")
        f.write("-" * 160 + "\n")
        f.write(f"{'Grid':<8} {'Used/n':<10} {'Cell':<11} {'Strategy':<14} {'Edge(h,v)':<12} "
                f"{'Cost Calculation':<60} {'Total':<10}\n")
        f.write("-" * 160 + "\n")

        for cfg in configs:
            grid = f"{cfg['cols']}×{cfg['rows']}"
            used_str = f"{cfg['used_images']}/{n}"
            cell_size = f"{cfg['cell_width']}×{cfg['cell_height']}"
            edge_adj = format_edge_adjustment(cfg['padding_h'], cfg['padding_v'], cfg['clip_h'], cfg['clip_v'])
            cost_calc = format_cost_calculation(
                cfg['omit_fraction'],
                cfg['padding_h'], cfg['padding_v'], cfg['clip_h'], cfg['clip_v'],
                cfg['total_score']
            )

            f.write(f"{grid:<8} {used_str:<10} {cell_size:<11} {cfg['strategy']:<14} {edge_adj:<12} "
                    f"{cost_calc:<60} {cfg['total_score']:<10.0f}\n")

    print(f"Full report written to: grid_optimization_report.txt")
    print(f"Total configurations: {len(configs)}\n")

    # Sort by score for top results
    configs.sort(key=lambda c: c['total_score'])

    # Show top 20
    print(f"Top 20 by total score:")
    print("-" * 160)
    print(f"{'Grid':<8} {'Used/n':<10} {'Cell':<11} {'Strategy':<14} {'Edge(h,v)':<12} "
          f"{'Cost Calculation':<60} {'Total':<10}")
    print("-" * 160)

    for cfg in configs[:20]:
        grid = f"{cfg['cols']}×{cfg['rows']}"
        used_str = f"{cfg['used_images']}/{n}"
        cell_size = f"{cfg['cell_width']}×{cfg['cell_height']}"
        edge_adj = format_edge_adjustment(cfg['padding_h'], cfg['padding_v'], cfg['clip_h'], cfg['clip_v'])
        cost_calc = format_cost_calculation(
            cfg['omit_fraction'],
            cfg['padding_h'], cfg['padding_v'], cfg['clip_h'], cfg['clip_v'],
            cfg['total_score']
        )

        print(f"{grid:<8} {used_str:<10} {cell_size:<11} {cfg['strategy']:<14} {edge_adj:<12} "
              f"{cost_calc:<60} {cfg['total_score']:<10.0f}")

    # Show winner
    best = configs[0]
    print(f"\n{'=' * 160}")
    print(f"WINNER: {best['cols']}×{best['rows']} grid, {best['cell_width']}×{best['cell_height']} cells, using {best['used_images']}/{n} images")
    print(f"{'=' * 160}")
    print(f"  Strategy: {best['strategy']}")
    print(f"  Omitted: {best['omitted_images']} ({100*best['omit_fraction']:.1f}%) → cost {best['omit_cost']:.1f}")

    edge_h = best['padding_h']/2 if best['padding_h'] > 0 else -best['clip_h']/2
    edge_v = best['padding_v']/2 if best['padding_v'] > 0 else -best['clip_v']/2

    if best['padding_h'] or best['padding_v']:
        if best['padding_h'] > 0:
            print(f"  Padding horizontal: {best['padding_h']/2:.0f}px per edge → cost {best['padding_h']:.1f}")
        if best['padding_v'] > 0:
            print(f"  Padding vertical: {best['padding_v']/2:.0f}px per edge → cost {best['padding_v']:.1f}")

    if best['clip_h'] or best['clip_v']:
        if best['clip_h'] > 0:
            print(f"  Clipping horizontal: {best['clip_h']/2:.0f}px per edge ({100*best['clip_fraction_h']:.1f}% of cell) → cost {best['clip_h']*0.5:.1f}")
            print(f"    (Affects {best['rows']} cells on left + {best['rows']} cells on right)")
        if best['clip_v'] > 0:
            print(f"  Clipping vertical: {best['clip_v']/2:.0f}px per edge ({100*best['clip_fraction_v']:.1f}% of cell) → cost {best['clip_v']*0.5:.1f}")
            print(f"    (Affects {best['cols']} cells on top + {best['cols']} cells on bottom)")

    print(f"  TOTAL: {best['total_score']:.1f}")
    print(f"\n  Memory: ~{best['used_images'] * best['cell_width'] * best['cell_height'] * 3 / 1024 / 1024:.0f}MB uncompressed")
    print()


if __name__ == '__main__':
    main()
