#!/bin/bash
# Benchmark montage with 37×27 grid, 111×148 cells, 999 images

set -e

echo "=========================================="
echo "Montage Benchmark: 999 images, 111×148 cells"
echo "Grid: 37×27"
echo "Target: 4096×4096 output"
echo "Strategy: clip_h_pad_v (-6px H per edge, +50px V per edge)"
echo "=========================================="

# Create test directory
TEST_DIR="/tmp/montage_benchmark_999_$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo
echo "Creating 999 test images (111×148)..."
for i in $(seq 1 999); do
    color=$(printf "rgb(%d,%d,%d)" $((i*37 % 256)) $((i*73 % 256)) $((i*113 % 256)))
    convert -size 111x148 "xc:$color" \
        -pointsize 12 -gravity center -annotate +0+0 "$i" \
        "input_$(printf '%04d' $i).jpg"

    if [ $((i % 100)) -eq 0 ]; then
        echo "  Created $i/999..."
    fi
done
echo "✓ Created 999 test images"

echo
echo "=========================================="
echo "Running montage + convert (two-step)"
echo "=========================================="

time_start=$(date +%s.%N)

# Step 1: Create collage (37×111 = 4107 wide, 27×148 = 3996 tall)
montage input_*.jpg \
  -tile 37x27 \
  -geometry 111x148+0+0 \
  -background gray \
  collage_temp.jpg

# Step 2: Fit to 4096×4096 (clip 11px H, pad 100px V)
convert collage_temp.jpg \
  -gravity center \
  -background gray \
  -extent 4107x4096 \
  -crop 4096x4096+5+0 \
  +repage \
  output_999.jpg

time_end=$(date +%s.%N)
elapsed=$(echo "$time_end - $time_start" | bc)

echo "✓ Complete: ${elapsed}s"
identify output_999.jpg
ls -lh output_999.jpg collage_temp.jpg

echo
echo "=========================================="
echo "Memory usage during run:"
free -h | grep "Mem:"

echo
echo "Test directory: $TEST_DIR"
echo "To cleanup: rm -rf $TEST_DIR"
