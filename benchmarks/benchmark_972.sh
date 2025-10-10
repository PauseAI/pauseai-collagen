#!/bin/bash
# Benchmark montage with 36×27 grid, 114×152 cells, 972 images

set -e

echo "=========================================="
echo "Montage Benchmark: 972 images, 114×152 cells"
echo "Grid: 36×27"
echo "Target: 4096×4096 output"
echo "Strategy: clip_both (-4px per edge)"
echo "=========================================="

# Create test directory
TEST_DIR="/tmp/montage_benchmark_972_$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo
echo "Creating 972 test images (114×152)..."
for i in $(seq 1 972); do
    color=$(printf "rgb(%d,%d,%d)" $((i*37 % 256)) $((i*73 % 256)) $((i*113 % 256)))
    convert -size 114x152 "xc:$color" \
        -pointsize 12 -gravity center -annotate +0+0 "$i" \
        "input_$(printf '%04d' $i).jpg"

    if [ $((i % 100)) -eq 0 ]; then
        echo "  Created $i/972..."
    fi
done
echo "✓ Created 972 test images"

echo
echo "=========================================="
echo "Running montage + convert (two-step)"
echo "=========================================="

time_start=$(date +%s.%N)

# Step 1: Create collage (36×114 = 4104 wide, 27×152 = 4104 tall)
montage input_*.jpg \
  -tile 36x27 \
  -geometry 114x152+0+0 \
  -background gray \
  collage_temp.jpg

# Step 2: Crop to 4096×4096 (clip 8px total, 4px per edge on both axes)
convert collage_temp.jpg \
  -gravity center \
  -crop 4096x4096+0+0 \
  +repage \
  output_972.jpg

time_end=$(date +%s.%N)
elapsed=$(echo "$time_end - $time_start" | bc)

echo "✓ Complete: ${elapsed}s"
identify output_972.jpg
ls -lh output_972.jpg collage_temp.jpg

echo
echo "=========================================="
echo "Memory usage during run:"
free -h | grep "Mem:"

echo
echo "Test directory: $TEST_DIR"
echo "To cleanup: rm -rf $TEST_DIR"
