#!/bin/bash
# Backfill: Generate 300×400 PNG tiles from existing sources JPEGs

set -e

CAMPAIGN="test_prototype"
APPROVED_DIR="/mnt/efs/$CAMPAIGN/sources"
TILES_DIR="/mnt/efs/$CAMPAIGN/tiles"

mkdir -p "$TILES_DIR"

echo "Backfilling tiles for $CAMPAIGN campaign"
echo "============================================================"
echo

jpg_count=$(ls -1 "$APPROVED_DIR"/*.jpg 2>/dev/null | wc -l)
echo "Found $jpg_count JPEG files in $APPROVED_DIR"

if [ $jpg_count -eq 0 ]; then
    echo "No JPEGs to process"
    exit 0
fi

echo "Generating 300×400 PNG tiles..."
echo

time_start=$(date +%s.%N)

counter=0
for jpg in "$APPROVED_DIR"/*.jpg; do
    basename=$(basename "$jpg" .jpg)
    png="$TILES_DIR/${basename}.png"

    convert "$jpg" -resize 300x400! "$png"

    counter=$((counter + 1))
    if [ $((counter % 10)) -eq 0 ]; then
        echo "  Created $counter/$jpg_count..."
    fi
done

time_end=$(date +%s.%N)
elapsed=$(echo "$time_end - $time_start" | bc)

echo
echo "✓ Created $counter tiles in ${elapsed}s"
echo "  Average: $(echo "scale=3; $elapsed / $counter" | bc)s per image"
echo

thumb_size=$(du -sh "$TILES_DIR" | cut -f1)
jpg_size=$(du -sh "$APPROVED_DIR" | cut -f1)

echo "Storage:"
echo "  Approved (JPEG):    $jpg_size"
echo "  Tiles (PNG):   $thumb_size"
