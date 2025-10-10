#!/usr/bin/env python3
"""
Benchmark ImageMagick montage performance at scale.

Tests collage generation with varying image counts and configurations.
"""

import subprocess
import time
import tempfile
import shutil
from pathlib import Path


def create_test_images(count: int, size: str = "1500x2000") -> Path:
    """Create test images in temp directory."""
    temp_dir = Path(tempfile.mkdtemp(prefix='montage_bench_'))

    print(f"Creating {count} test images ({size})...")
    for i in range(count):
        # Create simple colored image with text
        color = f"rgb({(i*37)%256},{(i*73)%256},{(i*113)%256})"
        output = temp_dir / f"test_{i:04d}.jpg"

        subprocess.run([
            'convert', '-size', size, f'xc:{color}',
            '-pointsize', '72', '-gravity', 'center',
            '-annotate', '+0+0', f'{i}',
            str(output)
        ], check=True, capture_output=True)

        if (i + 1) % 100 == 0:
            print(f"  Created {i + 1}/{count}...")

    print(f"✓ Created {count} images in {temp_dir}")
    return temp_dir


def benchmark_montage(image_dir: Path, output_file: str, tile_config: str = None):
    """
    Benchmark montage generation.

    Args:
        image_dir: Directory containing test images
        output_file: Output collage filename
        tile_config: Tile layout (e.g., "10x20" for 200 images)

    Returns:
        Elapsed time in seconds
    """
    images = sorted(image_dir.glob('*.jpg'))
    count = len(images)

    # Auto-calculate grid if not specified
    if not tile_config:
        # Aim for roughly square grid
        cols = int(count ** 0.5)
        rows = (count + cols - 1) // cols
        tile_config = f"{cols}x{rows}"

    cmd = [
        'montage',
        *[str(img) for img in images],
        '-tile', tile_config,
        '-geometry', '150x200+2+2',  # Smaller thumbs for grid
        '-background', 'gray',
        output_file
    ]

    print(f"\nRunning montage on {count} images (tile: {tile_config})...")
    start = time.time()

    result = subprocess.run(cmd, capture_output=True, text=True)

    elapsed = time.time() - start

    if result.returncode == 0:
        output_path = Path(output_file)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"✓ Montage complete: {elapsed:.2f}s")
        print(f"  Output: {output_file} ({size_mb:.1f} MB)")
    else:
        print(f"✗ Montage failed: {result.stderr}")

    return elapsed


def main():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("ImageMagick Montage Benchmark")
    print("=" * 80)

    # Test configurations
    test_configs = [
        (200, "14x15"),    # Current sayno scale
        (1000, "32x32"),   # 1k images
        (5000, "71x71"),   # 5k images (ambitious)
    ]

    results = []

    for count, tile in test_configs:
        print(f"\n{'=' * 80}")
        print(f"BENCHMARK: {count} images")
        print('=' * 80)

        # Create test images
        test_dir = create_test_images(count)

        try:
            # Run benchmark
            output = f'/tmp/montage_{count}.jpg'
            elapsed = benchmark_montage(test_dir, output, tile)

            results.append({
                'count': count,
                'time': elapsed,
                'per_image': elapsed / count * 1000  # ms per image
            })

            # Cleanup output
            Path(output).unlink(missing_ok=True)

        finally:
            # Cleanup test images
            shutil.rmtree(test_dir)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Count':<10} {'Time':<12} {'Per Image':<15} {'Accept in HTTP?'}")
    print("-" * 80)

    for r in results:
        timeout_ok = "✓ Yes (<30s)" if r['time'] < 30 else "✗ No (async needed)"
        print(f"{r['count']:<10} {r['time']:>8.2f}s    {r['per_image']:>8.2f}ms       {timeout_ok}")

    print("\n" + "=" * 80)
    print("Recommendation:")
    if results[-1]['time'] > 30:
        print("  Async background processing REQUIRED for large collages")
    else:
        print("  Synchronous processing OK with gunicorn multi-worker")


if __name__ == '__main__':
    main()
