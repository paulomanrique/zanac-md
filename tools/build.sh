#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/tools/env_mac.sh"

if [ ! -d "$GDK" ]; then
  echo "SGDK not found at $GDK"
  echo "Run: tools/setup_sgdk_mac.sh"
  exit 1
fi

cd "$ROOT"
python3 "$ROOT/tools/extract_logo.py" --asm "$ROOT/../zanac-re/source/zanac.asm" --out "$ROOT" 2>/dev/null || \
  python3 "$ROOT/tools/extract_logo.py" --out "$ROOT"
if command -v sips >/dev/null 2>&1; then
  python3 "$ROOT/tools/build_title_md.py" --out "$ROOT"
else
  echo "note: sips not found; using committed title_md_logo.png"
fi
make -f "$GDK/makefile.gen" "$@"
echo "Built: $ROOT/out/rom.bin"
