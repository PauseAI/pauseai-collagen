#!/bin/bash
# Benchmark collage generation from pre-generated 300×400 PNG thumbnails

set -e

THUMB_DIR="/mnt/efs/test_prototype/thumbnails"
WORK_DIR="/tmp/collage_from_pregenerated_$$"

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

echo "============================================================"
echo "Collage Benchmark from Pre-Generated 300×400 PNG Thumbnails"
echo "============================================================"
echo

# TEST 1: 221 images (17×13 grid, 237×316 tiles)
echo "TEST 1: 221 images → 17×13 grid, 237×316 tiles"
echo "------------------------------------------------------------"

mkdir -p tiles_221

echo "Step 1: Resize 221 thumbnails (300×400 → 237×316)..."
time_start=$(date +%s.%N)

thumbs=($THUMB_DIR/*.png)
for i in $(seq 0 220); do
    convert "${thumbs[$i]}" -resize 237x316! "tiles_221/tile_$(printf '%03d' $i).png"
done

time_tile_221=$(echo "$(date +%s.%N) - $time_start" | bc)
echo "  ✓ Tiles created: ${time_tile_221}s"

echo
echo "Step 2: Montage assembly..."
time_start=$(date +%s.%N)

montage tiles_221/*.png \
  -tile 17x13 \
  -geometry 237x316+0+0 \
  -background none \
  temp.png

convert temp.png \
  -gravity center \
  -background none \
  -extent 4096x4108 \
  -crop 4096x4096+0+6 \
  +repage \
  collage_221.png

time_montage_221=$(echo "$(date +%s.%N) - $time_start" | bc)
total_221=$(echo "$time_tile_221 + $time_montage_221" | bc)

echo "  ✓ Montage: ${time_montage_221}s"
echo "  TOTAL: ${total_221}s"

ls -lh collage_221.png

# TEST 2: 999 images (37×27 grid, 111×148 tiles)
echo
echo "TEST 2: 999 images → 37×27 grid, 111×148 tiles"
echo "------------------------------------------------------------"

mkdir -p tiles_999

echo "Step 1: Resize 999 thumbnails (300×400 → 111×148)..."
time_start=$(date +%s.%N)

for i in $(seq 0 998); do
    convert "${thumbs[$i]}" -resize 111x148! "tiles_999/tile_$(printf '%04d' $i).png"

    if [ $((i % 200)) -eq 0 ]; then
        echo "    Resized $i/999..."
    fi
done

time_tile_999=$(echo "$(date +%s.%N) - $time_start" | bc)
echo "  ✓ Tiles created: ${time_tile_999}s"

echo
echo "Step 2: Montage assembly..."
time_start=$(date +%s.%N)

montage tiles_999/*.png \
  -tile 37x27 \
  -geometry 111x148+0+0 \
  -background none \
  temp2.png

convert temp2.png \
  -gravity center \
  -background none \
  -extent 4107x4096 \
  -crop 4096x4096+5+0 \
  +repage \
  collage_999.png

time_montage_999=$(echo "$(date +%s.%N) - $time_start" | bc)
total_999=$(echo "$time_tile_999 + $time_montage_999" | bc)

echo "  ✓ Montage: ${time_montage_999}s"
echo "  TOTAL: ${total_999}s"

ls -lh collage_999.png

echo
echo "============================================================"
echo "SUMMARY: Collage from Pre-Generated Thumbnails"
echo "============================================================"
echo "221 images:"
echo "  Tile resize:  ${time_tile_221}s"
echo "  Montage:      ${time_montage_221}s"
echo "  TOTAL:        ${total_221}s"
echo
echo "999 images:"
echo "  Tile resize:  ${time_tile_999}s"
echo "  Montage:      ${time_montage_999}s"
echo "  TOTAL:        ${total_999}s"
echo
echo "Memory:"
free -h | grep Mem:
echo
echo "Work dir: $WORK_DIR"
