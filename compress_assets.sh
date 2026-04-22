#!/bin/bash
# Run this after adding new images or videos to Assets/
# Usage: ./compress_assets.sh

export PATH="/opt/homebrew/bin:$PATH"

ASSETS="$(dirname "$0")/Assets"
HTML_DIR="$(dirname "$0")"

echo "Scanning for uncompressed files in Assets/..."

# PNGs → WebP
find "$ASSETS" -iname "*.png" | while read f; do
  webp="${f%.png}.webp"
  echo "  Converting: $(basename "$f") → $(basename "$webp")"
  cwebp -q 82 "$f" -o "$webp" -quiet
  rm "$f"
  # Update HTML references
  fname=$(basename "$f")
  wname=$(basename "$webp")
  for html in "$HTML_DIR"/*.html; do
    sed -i '' "s|${fname}|${wname}|g" "$html"
  done
done

# Large JPGs/JPEGs (over 1MB) → recompress
find "$ASSETS" \( -iname "*.jpg" -o -iname "*.jpeg" \) | while read f; do
  size=$(stat -f%z "$f")
  if [ "$size" -gt 1048576 ]; then
    echo "  Compressing: $(basename "$f")"
    sips -s format jpeg -s formatOptions 82 "$f" --out "$f" > /dev/null
  fi
done

# MP4s → H.264 (skips already-compressed ones based on bitrate)
find "$ASSETS" -iname "*.mp4" | while read f; do
  size=$(stat -f%z "$f")
  duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null)
  if [ -n "$duration" ] && [ "$size" -gt 5242880 ]; then
    bitrate=$(echo "$size $duration" | awk '{printf "%d", ($1*8)/($2*1000)}')
    if [ "$bitrate" -gt 3000 ]; then
      echo "  Compressing video: $(basename "$f")"
      tmp="${f%.mp4}_tmp.mp4"
      ffmpeg -i "$f" -vcodec libx264 -crf 26 -preset fast -acodec aac -b:a 128k "$tmp" -y -loglevel error
      mv "$tmp" "$f"
    fi
  fi
done

echo ""
echo "Done. Run 'git add -A && git commit' when ready to push."
