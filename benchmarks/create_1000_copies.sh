#!/bin/bash
# Create 1000 copies of real test photos

set -e

APPROVED_DIR="/mnt/efs/test_prototype/sources"
COPY_DIR="/tmp/test_photos_1000"

# Count real photos
REAL_COUNT=$(ls -1 $APPROVED_DIR/*.jpg 2>/dev/null | wc -l)
echo "Real photos available: $REAL_COUNT"

if [ $REAL_COUNT -lt 5 ]; then
    echo "❌ Not enough photos in $APPROVED_DIR"
    exit 1
fi

# Create/clear copy directory
mkdir -p "$COPY_DIR"
rm -f "$COPY_DIR"/*.jpg

echo "Creating 1000 copies..."

counter=1
while [ $counter -le 1000 ]; do
    # Pick a random photo from sources dir
    photo=$(ls -1 $APPROVED_DIR/*.jpg | shuf -n 1)
    cp "$photo" "$COPY_DIR/photo_$(printf '%04d' $counter).jpg"

    if [ $((counter % 100)) -eq 0 ]; then
        echo "  Created $counter/1000..."
    fi

    counter=$((counter + 1))
done

actual=$(ls -1 "$COPY_DIR"/*.jpg | wc -l)
total_size=$(du -sh "$COPY_DIR" | cut -f1)

echo "✓ Created $actual copies in $COPY_DIR"
echo "  Total size: $total_size"
echo
echo "These copies can be reused for multiple benchmarks"
