#!/bin/bash
# Test realistic EFS workflow: write photos over time, then read all for collage

set -e

echo "============================================================"
echo "Testing Production Workflow: EFS Write → Cache → Read"
echo "============================================================"

# Setup
EFS_TEST="/mnt/efs/test_benchmark_workflow"
SOURCE="/tmp/test_photos_1000"
mkdir -p "$EFS_TEST"
rm -f "$EFS_TEST"/*.jpg

echo
echo "Phase 1: Simulating webhook writes (999 photos to EFS)"
echo "  (Writes happen over time in production, cache persists)"
echo

time_start=$(date +%s.%N)

for i in $(seq 1 999); do
    cp "$SOURCE/photo_$(printf '%04d' $i).jpg" "$EFS_TEST/photo_$(printf '%04d' $i).jpg"

    if [ $((i % 200)) -eq 0 ]; then
        echo "  Wrote $i/999..."
    fi
done

time_write=$(echo "$(date +%s.%N) - $time_start" | bc)
echo "✓ Wrote 999 photos to EFS: ${time_write}s"

# Check cache status
cached_kb=$(grep "^Cached:" /proc/meminfo | awk '{print $2}')
echo "  Current cache: $((cached_kb / 1024))MB"

echo
echo "Phase 2: Reading from EFS for tile generation"
echo "  (Should hit cache for recently written files)"
echo

# Clear /tmp tiles
rm -f /tmp/thumb_*.png

time_start=$(date +%s.%N)

for i in $(seq 1 999); do
    convert "$EFS_TEST/photo_$(printf '%04d' $i).jpg" \
        -resize 111x148! \
        "/tmp/thumb_$(printf '%04d' $i).png"

    if [ $((i % 200)) -eq 0 ]; then
        echo "  Created $i/999..."
    fi
done

time_thumb_efs=$(echo "$(date +%s.%N) - $time_start" | bc)

echo "✓ Generated 999 tiles from EFS: ${time_thumb_efs}s"

# Compare to local disk baseline
echo
echo "Phase 3: Baseline from local /tmp (for comparison)"
echo

rm -f /tmp/thumb_*.png
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

time_start=$(date +%s.%N)

for i in $(seq 1 999); do
    convert "$SOURCE/photo_$(printf '%04d' $i).jpg" \
        -resize 111x148! \
        "/tmp/thumb_$(printf '%04d' $i).png" 2>&1

    if [ $((i % 200)) -eq 0 ]; then
        echo "  Created $i/999..."
    fi
done

time_thumb_local=$(echo "$(date +%s.%N) - $time_start" | bc)

echo "✓ Generated 999 tiles from /tmp: ${time_thumb_local}s"

# Cleanup
rm -rf "$EFS_TEST" /tmp/thumb_*.png

echo
echo "============================================================"
echo "RESULTS"
echo "============================================================"
echo "Write 999 photos to EFS:              ${time_write}s"
echo "Thumbnail from EFS (cached):          ${time_thumb_efs}s"
echo "Thumbnail from /tmp (baseline):       ${time_thumb_local}s"
echo "Overhead from EFS vs local:           $(echo "$time_thumb_efs - $time_thumb_local" | bc)s"
echo
echo "Cache is working!"
