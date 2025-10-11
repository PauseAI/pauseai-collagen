#!/bin/bash
# Create 1000 tile copies from 19 real tiles

set -e

TILES_DIR="/mnt/efs/test_prototype/tiles"
REAL_COUNT=$(ls -1 "$TILES_DIR"/*.png 2>/dev/null | wc -l)

echo "Creating 1000 tile copies from $REAL_COUNT real tiles..."

if [ $REAL_COUNT -lt 5 ]; then
    echo "❌ Not enough tiles in $TILES_DIR"
    exit 1
fi

counter=1
while [ $counter -le 1000 ]; do
    # Pick random tile
    source=$(ls -1 "$TILES_DIR"/*.png | shuf -n 1)
    cp "$source" "$TILES_DIR/copy_$(printf '%04d' $counter).png"

    if [ $((counter % 100)) -eq 0 ]; then
        echo "  Created $counter/1000..."
    fi

    counter=$((counter + 1))
done

actual=$(ls -1 "$TILES_DIR"/*.png | wc -l)
total_size=$(du -sh "$TILES_DIR" | cut -f1)

echo "✓ Created $actual total tiles in $TILES_DIR"
echo "  Total size: $total_size"
