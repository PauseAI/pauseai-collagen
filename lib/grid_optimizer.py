"""
Grid layout optimizer for collage generation.

Adapted from tools/optimize_grid_v3.py to be usable as a library.
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


def get_top_layouts(n_images: int, target_size: int = 4096, top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Get the top N best layouts for a given number of images.

    Args:
        n_images: Number of images to include in collage
        target_size: Target collage dimension (square, default 4096)
        top_n: Number of top layouts to return (default 3)

    Returns:
        List of top layouts sorted by total_score (best first)
    """
    all_configs = optimize_for_n_images(n_images, target_size)
    all_configs.sort(key=lambda c: c['total_score'])
    return all_configs[:top_n]


def evaluate_custom_grid(cols: int, rows: int, n_images: int, target_size: int = 4096) -> Dict[str, Any]:
    """
    Evaluate a custom grid layout specified by user.

    Args:
        cols: Number of columns
        rows: Number of rows
        n_images: Total images available
        target_size: Target collage dimension (square, default 4096)

    Returns:
        Configuration dict with costs and geometry
    """
    grid_slots = cols * rows
    used_images = min(grid_slots, n_images)
    omitted = n_images - used_images
    omit_fraction = omitted / n_images
    omit_cost = OMIT_BASE_COST * omit_fraction

    # Find best k for this grid
    k_configs = explore_grid_k_range(cols, rows, target_size)

    if not k_configs:
        return None  # Grid doesn't work (too much clipping)

    # Use the config with best fit_cost
    best_cfg = min(k_configs, key=lambda c: c['fit_cost'])

    total_score = omit_cost + best_cfg['fit_cost']

    return {
        'cols': cols,
        'rows': rows,
        'grid_slots': grid_slots,
        'used_images': used_images,
        'omitted_images': omitted,
        'omit_fraction': omit_fraction,
        'omit_cost': omit_cost,
        'total_score': total_score,
        **best_cfg
    }


def format_layout_description(layout: Dict[str, Any]) -> str:
    """
    Format a human-readable description of a layout.

    Args:
        layout: Layout configuration dict

    Returns:
        Multi-line string describing the layout
    """
    lines = []
    lines.append(f"{layout['cols']}×{layout['rows']} grid ({layout['used_images']} images, {layout['cell_width']}×{layout['cell_height']}px cells)")
    lines.append(f"  Collage: {layout['collage_width']}×{layout['collage_height']}px")
    lines.append(f"  Strategy: {layout['strategy']}")

    if layout['omitted_images'] > 0:
        lines.append(f"  Omitted: {layout['omitted_images']} images ({100*layout['omit_fraction']:.1f}%)")

    if layout['padding_h'] > 0:
        lines.append(f"  Padding H: {layout['padding_h']/2:.0f}px per edge")
    if layout['padding_v'] > 0:
        lines.append(f"  Padding V: {layout['padding_v']/2:.0f}px per edge")

    if layout['clip_h'] > 0:
        lines.append(f"  Clipping H: {layout['clip_h']/2:.0f}px per edge ({100*layout['clip_fraction_h']:.1f}% of cell)")
    if layout['clip_v'] > 0:
        lines.append(f"  Clipping V: {layout['clip_v']/2:.0f}px per edge ({100*layout['clip_fraction_v']:.1f}% of cell)")

    lines.append(f"  Score: {layout['total_score']:.1f}")

    return "\n".join(lines)
