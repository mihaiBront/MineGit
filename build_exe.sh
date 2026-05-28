#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_IMAGE="${DOCKER_IMAGE:-cdrx/pyinstaller-windows:python3}"
CONTAINER_NAME="minegit-win-build-$$"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to build a Windows executable from Linux."
  exit 1
fi

echo "[build_exe.sh] Building Windows executable using Docker image: $DOCKER_IMAGE"

docker run --rm \
  --name "$CONTAINER_NAME" \
  -v "$SCRIPT_DIR:/src" \
  -w /src \
  "$DOCKER_IMAGE" \
  "pip install -r src/requirements.txt && pyinstaller --noconfirm --clean --onefile --windowed --name MineGit --distpath dist --workpath build/pyinstaller-linux-win --specpath build/pyinstaller-spec-linux-win src/MineGit.py"

if [[ -f "$SCRIPT_DIR/dist/MineGit.exe" ]]; then
  echo "[build_exe.sh] Done. Windows executable generated at: $SCRIPT_DIR/dist/MineGit.exe"
  exit 0
fi

echo "[build_exe.sh] Build completed, but dist/MineGit.exe was not found."
echo "[build_exe.sh] Check container logs and dist/ contents for details."
exit 1
