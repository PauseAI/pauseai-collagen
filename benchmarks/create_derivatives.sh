#!/bin/bash
# Create derivative images from 4K PNG master (crop padding, resize, convert to JPEG)

set -e

if [ $# -lt 3 ]; then
    echo "Usage: $0 <input.png> <output.jpg> <target_size>"
    echo "Example: $0 collage_4k.png collage_1080p.jpg 1920"
    exit 1
fi

INPUT="$1"
OUTPUT="$2"
TARGET_SIZE="$3"

if [ ! -f "$INPUT" ]; then
    echo "❌ Input file not found: $INPUT"
    exit 1
fi

echo "Creating derivative from $INPUT"
echo "  Target size: ${TARGET_SIZE}px"
echo "  Output: $OUTPUT"
echo

time_start=$(date +%s.%N)

# Step 1: Trim transparent padding
echo "Step 1: Trimming transparent padding..."
convert "$INPUT" \
    -trim \
    +repage \
    "${OUTPUT%.jpg}_trimmed.png"

trimmed_size=$(identify -format "%wx%h" "${OUTPUT%.jpg}_trimmed.png")
echo "  Trimmed to: $trimmed_size"

# Step 2: Resize to target (maintaining aspect ratio)
echo
echo "Step 2: Resizing to ${TARGET_SIZE}px..."
convert "${OUTPUT%.jpg}_trimmed.png" \
    -resize "${TARGET_SIZE}x${TARGET_SIZE}" \
    -quality 90 \
    "$OUTPUT"

final_size=$(identify -format "%wx%h" "$OUTPUT")
echo "  Final size: $final_size"

# Cleanup intermediate
rm "${OUTPUT%.jpg}_trimmed.png"

time_end=$(date +%s.%N)
elapsed=$(echo "$time_end - $time_start" | bc)

echo
echo "✓ Complete: ${elapsed}s"
ls -lh "$OUTPUT"

# Show file sizes
input_size=$(ls -lh "$INPUT" | awk '{print $5}')
output_size=$(ls -lh "$OUTPUT" | awk '{print $5}')
echo
echo "Size comparison:"
echo "  Input (4K PNG):    $input_size"
echo "  Output (JPEG):     $output_size"
