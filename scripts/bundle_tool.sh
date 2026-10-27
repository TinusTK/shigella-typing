#!/usr/bin/env bash
# Assemble a Galaxy-installable tool directory with the panels bundled:
#   bash scripts/bundle_tool.sh [outdir]   -> <outdir>/shigella_typing/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/build}"
DEST="$OUT/shigella_typing"
[ -f "$ROOT/panels/manifest.json" ] || {
  echo "panels/ is empty - populate it first (see panels/README.md)" >&2; exit 1; }
rm -rf "$DEST" && mkdir -p "$DEST"
cp "$ROOT"/tool/*.xml "$ROOT"/.shed.yml "$ROOT"/LICENSE "$DEST"/
cp -r "$ROOT"/tool/shigella_typing "$DEST"/shigella_typing
cp -r "$ROOT"/tool/test-data "$DEST"/
cp -r "$ROOT"/panels "$DEST"/panels
find "$DEST" -name __pycache__ -prune -exec rm -rf {} +
echo "Bundled tool at $DEST"
