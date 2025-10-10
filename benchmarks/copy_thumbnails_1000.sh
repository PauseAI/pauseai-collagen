#!/bin/bash
# Create 1000 thumbnail copies from 19 real thumbnails

set -e

THUMB_DIR="/mnt/efs/test_prototype/thumbnails"
REAL_COUNT=$(ls -1 "$THUMB_DIR"/*.png 2>/dev/null | wc -l)

echo "Creating 1000 thumbnail copies from $REAL_COUNT real thumbnails..."

if [ $REAL_COUNT -lt 5 ]; then
    echo "❌ Not enough thumbnails in $THUMB_DIR"
    exit 1
fi

counter=1
while [ $counter -le 1000 ]; do
    # Pick random thumbnail
    source=$(ls -1 "$THUMB_DIR"/*.png | shuf -n 1)
    cp "$source" "$THUMB_DIR/copy_$(printf '%04d' $counter).png"

    if [ $((counter % 100)) -eq 0 ]; then
        echo "  Created $counter/1000..."
    fi

    counter=$((counter + 1))
done

actual=$(ls -1 "$THUMB_DIR"/*.png | wc -l)
total_size=$(du -sh "$THUMB_DIR" | cut -f1)

echo "✓ Created $actual total thumbnails in $THUMB_DIR"
echo "  Total size: $total_size"
