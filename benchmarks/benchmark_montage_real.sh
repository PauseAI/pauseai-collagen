#!/bin/bash
# Benchmark montage with realistic 17×13 grid, 237×316 cells, 221 images

set -e

echo "=========================================="
echo "Montage Benchmark: 221 images, 237×316 cells"
echo "Target: 4096×4096 output"
echo "=========================================="

# Create test directory
TEST_DIR="/tmp/montage_benchmark_$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo
echo "Creating 221 test images (237×316)..."
for i in $(seq 1 221); do
    color=$(printf "rgb(%d,%d,%d)" $((i*37 % 256)) $((i*73 % 256)) $((i*113 % 256)))
    convert -size 237x316 "xc:$color" \
        -pointsize 24 -gravity center -annotate +0+0 "$i" \
        "input_$(printf '%03d' $i).jpg"

    if [ $((i % 50)) -eq 0 ]; then
        echo "  Created $i/221..."
    fi
done
echo "✓ Created 221 test images"

echo
echo "=========================================="
echo "APPROACH 1: Two-step (montage + convert)"
echo "=========================================="

time_start=$(date +%s.%N)

# Step 1: Create collage (17×237 = 4029 wide, 13×316 = 4108 tall)
montage input_*.jpg \
  -tile 17x13 \
  -geometry 237x316+0+0 \
  -background gray \
  collage_temp.jpg

# Step 2: Fit to 4096×4096 (pad 67px H, crop 12px V)
convert collage_temp.jpg \
  -gravity center \
  -background gray \
  -extent 4096x4108 \
  -crop 4096x4096+0+6 \
  +repage \
  output_twostep.jpg

time_end=$(date +%s.%N)
time_twostep=$(echo "$time_end - $time_start" | bc)

echo "✓ Two-step complete: ${time_twostep}s"
identify output_twostep.jpg
ls -lh output_twostep.jpg

echo
echo "=========================================="
echo "APPROACH 2: Single montage command"
echo "=========================================="

time_start=$(date +%s.%N)

montage input_*.jpg \
  -tile 17x13 \
  -geometry 237x316+0+0 \
  -background gray \
  -resize 4096x4096^ \
  -gravity center \
  -extent 4096x4096 \
  output_single.jpg

time_end=$(date +%s.%N)
time_single=$(echo "$time_end - $time_start" | bc)

echo "✓ Single command complete: ${time_single}s"
identify output_single.jpg
ls -lh output_single.jpg

echo
echo "=========================================="
echo "Comparing outputs"
echo "=========================================="

# Check if outputs are identical
if cmp -s output_twostep.jpg output_single.jpg; then
    echo "✓ Outputs are IDENTICAL (byte-for-byte match)"
else
    echo "⚠ Outputs differ"

    # Calculate perceptual difference if they differ
    compare -metric RMSE output_twostep.jpg output_single.jpg diff.jpg 2>&1 || true
    echo "  (Difference image saved to diff.jpg)"
fi

echo
echo "=========================================="
echo "BENCHMARK SUMMARY"
echo "=========================================="
echo "  Two-step approach:   ${time_twostep}s"
echo "  Single command:      ${time_single}s"
echo "  Test directory:      $TEST_DIR"
echo
echo "  Memory used (approx):"
free -h | grep "Mem:"

# Don't auto-cleanup so we can inspect results
echo
echo "To cleanup: rm -rf $TEST_DIR"
