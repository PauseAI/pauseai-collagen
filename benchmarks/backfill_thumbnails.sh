#!/bin/bash
# Backfill: Generate 300×400 PNG thumbnails from existing approved JPEGs

set -e

CAMPAIGN="test_prototype"
APPROVED_DIR="/mnt/efs/$CAMPAIGN/approved"
THUMB_DIR="/mnt/efs/$CAMPAIGN/thumbnails"

mkdir -p "$THUMB_DIR"

echo "Backfilling thumbnails for $CAMPAIGN campaign"
echo "============================================================"
echo

jpg_count=$(ls -1 "$APPROVED_DIR"/*.jpg 2>/dev/null | wc -l)
echo "Found $jpg_count JPEG files in $APPROVED_DIR"

if [ $jpg_count -eq 0 ]; then
    echo "No JPEGs to process"
    exit 0
fi

echo "Generating 300×400 PNG thumbnails..."
echo

time_start=$(date +%s.%N)

counter=0
for jpg in "$APPROVED_DIR"/*.jpg; do
    basename=$(basename "$jpg" .jpg)
    png="$THUMB_DIR/${basename}.png"

    convert "$jpg" -resize 300x400! "$png"

    counter=$((counter + 1))
    if [ $((counter % 10)) -eq 0 ]; then
        echo "  Created $counter/$jpg_count..."
    fi
done

time_end=$(date +%s.%N)
elapsed=$(echo "$time_end - $time_start" | bc)

echo
echo "✓ Created $counter thumbnails in ${elapsed}s"
echo "  Average: $(echo "scale=3; $elapsed / $counter" | bc)s per image"
echo

thumb_size=$(du -sh "$THUMB_DIR" | cut -f1)
jpg_size=$(du -sh "$APPROVED_DIR" | cut -f1)

echo "Storage:"
echo "  Approved (JPEG):    $jpg_size"
echo "  Thumbnails (PNG):   $thumb_size"
