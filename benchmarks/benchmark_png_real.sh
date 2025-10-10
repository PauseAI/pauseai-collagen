#!/bin/bash
# Benchmark PNG collage generation with real photos

set -e

SOURCE_DIR="/tmp/test_photos_1000"
WORK_DIR="/tmp/png_benchmark_$$"

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "============================================================"
echo "PNG Collage Benchmark with Real Photos"
echo "============================================================"

# TEST 1: 221 images (17×13 grid, 237×316 thumbnails)
echo
echo "=========================================="
echo "TEST 1: 221 images (17×13 grid, 237×316 cells)"
echo "=========================================="

mkdir -p test_221/thumbs

echo "Step 1: Creating 221 PNG thumbnails (237×316)..."
time_start=$(date +%s.%N)

for i in $(seq 1 221); do
    convert "$SOURCE_DIR/photo_$(printf '%04d' $i).jpg" \
        -resize 237x316! \
        "test_221/thumbs/thumb_$(printf '%03d' $i).png"
done

time_thumb_221=$(echo "$(date +%s.%N) - $time_start" | bc)
thumb_size_221=$(du -sh test_221/thumbs | cut -f1)
echo "  ✓ Thumbnails: ${time_thumb_221}s ($thumb_size_221)"

echo
echo "Step 2: Assembling PNG collage..."
time_start=$(date +%s.%N)

# Collage: 17×237 = 4029 wide, 13×316 = 4108 tall
montage test_221/thumbs/*.png \
  -tile 17x13 \
  -geometry 237x316+0+0 \
  -background none \
  test_221/collage_temp.png

# Fit to 4096×4096 (pad 67px H, crop 12px V)
convert test_221/collage_temp.png \
  -gravity center \
  -background none \
  -extent 4096x4108 \
  -crop 4096x4096+0+6 \
  +repage \
  test_221/final.png

time_montage_221=$(echo "$(date +%s.%N) - $time_start" | bc)
echo "  ✓ Montage: ${time_montage_221}s"

total_221=$(echo "$time_thumb_221 + $time_montage_221" | bc)

echo
identify test_221/final.png
ls -lh test_221/final.png

# TEST 2: 999 images (37×27 grid, 111×148 thumbnails)
echo
echo "=========================================="
echo "TEST 2: 999 images (37×27 grid, 111×148 cells)"
echo "=========================================="

mkdir -p test_999/thumbs

echo "Step 1: Creating 999 PNG thumbnails (111×148)..."
time_start=$(date +%s.%N)

for i in $(seq 1 999); do
    convert "$SOURCE_DIR/photo_$(printf '%04d' $i).jpg" \
        -resize 111x148! \
        "test_999/thumbs/thumb_$(printf '%04d' $i).png"

    if [ $((i % 200)) -eq 0 ]; then
        echo "    Created $i/999..."
    fi
done

time_thumb_999=$(echo "$(date +%s.%N) - $time_start" | bc)
thumb_size_999=$(du -sh test_999/thumbs | cut -f1)
echo "  ✓ Thumbnails: ${time_thumb_999}s ($thumb_size_999)"

echo
echo "Step 2: Assembling PNG collage..."
time_start=$(date +%s.%N)

# Collage: 37×111 = 4107 wide, 27×148 = 3996 tall
montage test_999/thumbs/*.png \
  -tile 37x27 \
  -geometry 111x148+0+0 \
  -background none \
  test_999/collage_temp.png

# Fit to 4096×4096 (crop 11px H, pad 100px V transparent)
convert test_999/collage_temp.png \
  -gravity center \
  -background none \
  -extent 4107x4096 \
  -crop 4096x4096+5+0 \
  +repage \
  test_999/final.png

time_montage_999=$(echo "$(date +%s.%N) - $time_start" | bc)
echo "  ✓ Montage: ${time_montage_999}s"

total_999=$(echo "$time_thumb_999 + $time_montage_999" | bc)

echo
identify test_999/final.png
ls -lh test_999/final.png

# SUMMARY
echo
echo "============================================================"
echo "SUMMARY"
echo "============================================================"
echo "221 images:"
echo "  Thumbnails: ${time_thumb_221}s ($thumb_size_221)"
echo "  Montage:    ${time_montage_221}s"
echo "  TOTAL:      ${total_221}s"
echo "  Final PNG:  $(ls -lh test_221/final.png | awk '{print $5}')"
echo
echo "999 images:"
echo "  Thumbnails: ${time_thumb_999}s ($thumb_size_999)"
echo "  Montage:    ${time_montage_999}s"
echo "  TOTAL:      ${total_999}s"
echo "  Final PNG:  $(ls -lh test_999/final.png | awk '{print $5}')"
echo
echo "Memory after tests:"
free -h | grep "Mem:"
echo
echo "Work directory: $WORK_DIR"
echo "Cleanup: rm -rf $WORK_DIR"
