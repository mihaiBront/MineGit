#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGETS=(
  "$SCRIPT_DIR/build"
  "$SCRIPT_DIR/dist"
  "$SCRIPT_DIR/.tools"
  "$SCRIPT_DIR/.venv-build"
  "$SCRIPT_DIR/.venv-build-win"
)

echo "[clean_build_products] Removing build artifacts..."
for target in "${TARGETS[@]}"; do
  if [[ -e "$target" ]]; then
    rm -rf "$target"
    echo "  removed: $target"
  else
    echo "  skipped: $target (not found)"
  fi
done

echo "[clean_build_products] Done."
