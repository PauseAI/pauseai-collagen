#!/bin/bash
# Benchmark montage with PNG output and transparent padding

set -e

echo "============================================================"
echo "PNG Montage Benchmark: Two test cases"
echo "============================================================"

# Test 1: 221 images (17×13 grid, 237×316 cells)
echo
echo "=========================================="
echo "TEST 1: 221 images, 237×316 cells"
echo "Grid: 17×13"
echo "Strategy: clip_v_pad_h (+34px H, -6px V per edge)"
echo "=========================================="

TEST_DIR_221="/tmp/montage_png_221_$$"
mkdir -p "$TEST_DIR_221"
cd "$TEST_DIR_221"

echo "Creating 221 PNG test images (237×316)..."
for i in $(seq 1 221); do
    color=$(printf "rgb(%d,%d,%d)" $((i*37 % 256)) $((i*73 % 256)) $((i*113 % 256)))
    convert -size 237x316 "xc:$color" \
        -pointsize 24 -gravity center -annotate +0+0 "$i" \
        "input_$(printf '%03d' $i).png"

    if [ $((i % 50)) -eq 0 ]; then
        echo "  Created $i/221..."
    fi
done
echo "✓ Created 221 PNG images"

echo
echo "Running montage with transparent padding..."
time_start=$(date +%s.%N)

# Create collage (17×237 = 4029 wide, 13×316 = 4108 tall)
montage input_*.png \
  -tile 17x13 \
  -geometry 237x316+0+0 \
  -background none \
  collage_temp.png

# Fit to 4096×4096 (pad 67px H transparent, crop 12px V)
convert collage_temp.png \
  -gravity center \
  -background none \
  -extent 4096x4108 \
  -crop 4096x4096+0+6 \
  +repage \
  output_221.png

time_end=$(date +%s.%N)
elapsed_221=$(echo "$time_end - $time_start" | bc)

echo "✓ Complete: ${elapsed_221}s"
identify output_221.png
ls -lh output_221.png collage_temp.png

# Test 2: 999 images (37×27 grid, 111×148 cells)
echo
echo "=========================================="
echo "TEST 2: 999 images, 111×148 cells"
echo "Grid: 37×27"
echo "Strategy: clip_h_pad_v (-6px H, +50px V per edge)"
echo "=========================================="

TEST_DIR_999="/tmp/montage_png_999_$$"
mkdir -p "$TEST_DIR_999"
cd "$TEST_DIR_999"

echo "Creating 999 PNG test images (111×148)..."
for i in $(seq 1 999); do
    color=$(printf "rgb(%d,%d,%d)" $((i*37 % 256)) $((i*73 % 256)) $((i*113 % 256)))
    convert -size 111x148 "xc:$color" \
        -pointsize 12 -gravity center -annotate +0+0 "$i" \
        "input_$(printf '%04d' $i).png"

    if [ $((i % 100)) -eq 0 ]; then
        echo "  Created $i/999..."
    fi
done
echo "✓ Created 999 PNG images"

echo
echo "Running montage with transparent padding..."
time_start=$(date +%s.%N)

# Create collage (37×111 = 4107 wide, 27×148 = 3996 tall)
montage input_*.png \
  -tile 37x27 \
  -geometry 111x148+0+0 \
  -background none \
  collage_temp.png

# Fit to 4096×4096 (clip 11px H, pad 100px V transparent)
convert collage_temp.png \
  -gravity center \
  -background none \
  -extent 4107x4096 \
  -crop 4096x4096+5+0 \
  +repage \
  output_999.png

time_end=$(date +%s.%N)
elapsed_999=$(echo "$time_end - $time_start" | bc)

echo "✓ Complete: ${elapsed_999}s"
identify output_999.png
ls -lh output_999.png collage_temp.png

echo
echo "============================================================"
echo "SUMMARY"
echo "============================================================"
echo "  221 images: ${elapsed_221}s"
echo "  999 images: ${elapsed_999}s"
echo
echo "Memory after tests:"
free -h | grep "Mem:"

echo
echo "Output files:"
echo "  221: $TEST_DIR_221/output_221.png"
echo "  999: $TEST_DIR_999/output_999.png"
echo
echo "Cleanup: rm -rf /tmp/montage_png_*"
