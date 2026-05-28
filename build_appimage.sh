#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_VENV="$SCRIPT_DIR/.venv-build"
APP_NAME="MineGit"
APPDIR="$SCRIPT_DIR/build/${APP_NAME}.AppDir"
DIST_DIR="$SCRIPT_DIR/dist"
TOOLS_DIR="$SCRIPT_DIR/.tools"
ICON_PATH="$SCRIPT_DIR/src/assets/minegit.png"
PYINSTALLER_DIST="$SCRIPT_DIR/dist/$APP_NAME"
PYINSTALLER_WORK="$SCRIPT_DIR/build/pyinstaller"
PYINSTALLER_SPEC="$SCRIPT_DIR/build/pyinstaller-spec"
ARCH="$(uname -m)"

if [[ "$ARCH" == "x86_64" ]]; then
  APPIMAGE_ARCH="x86_64"
elif [[ "$ARCH" == "aarch64" ]]; then
  APPIMAGE_ARCH="aarch64"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

mkdir -p "$TOOLS_DIR" "$DIST_DIR" "$SCRIPT_DIR/build" "$SCRIPT_DIR/src/assets"

if [[ ! -d "$BUILD_VENV" ]]; then
  python3 -m venv "$BUILD_VENV"
fi

"$BUILD_VENV/bin/python" -m pip install --upgrade pip
"$BUILD_VENV/bin/python" -m pip install -r "$SCRIPT_DIR/src/requirements.txt" pyinstaller

if [[ ! -f "$ICON_PATH" ]]; then
  "$BUILD_VENV/bin/python" - <<'PY'
import base64
from pathlib import Path

icon_data = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAx0lEQVR4nO3YQQ7CIBAF0dT6/1+2"
    "Y8cQ2JUEHCxY20nm6x0C+U8lY4sA4M9QvPj4FKwNfXx5CQAAAAAAAAAAfN5yVjv5Y8i0h3xQx+4f"
    "5xwJf2W9i6f4tR2lY+1M3oL9eE9m4bqv9Qv1b4N5qQxQw9X0Qm+F3Z3j+Rk4m3Wf+G9R6k9nS4JpA"
    "7Y2vO6fW6wW0n+z2mHjNnYBv7Jq8hP8Xqj9m9S2n7M7h7z0AAAAAAAAAAAD4W/4Aq2F5Q4YhGf0A"
    "AAAASUVORK5CYII="
)
path = Path("src/assets/minegit.png")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(base64.b64decode(icon_data))
PY
fi

rm -rf "$PYINSTALLER_WORK" "$PYINSTALLER_SPEC" "$PYINSTALLER_DIST" "$APPDIR"
"$BUILD_VENV/bin/pyinstaller" \
  --noconfirm \
  --clean \
  --windowed \
  --name "$APP_NAME" \
  --distpath "$SCRIPT_DIR/dist" \
  --workpath "$PYINSTALLER_WORK" \
  --specpath "$PYINSTALLER_SPEC" \
  "$SCRIPT_DIR/src/MineGit.py"

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
# Copy the whole onedir payload (binary + _internal runtime libs).
cp -a "$PYINSTALLER_DIST/." "$APPDIR/usr/bin/"
cp "$ICON_PATH" "$APPDIR/usr/share/icons/hicolor/256x256/apps/minegit.png"
cp "$ICON_PATH" "$APPDIR/minegit.png"
ln -sf "usr/share/icons/hicolor/256x256/apps/minegit.png" "$APPDIR/.DirIcon"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/MineGit" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/minegit.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=MineGit
Comment=Use Git as a Minecraft world host lock manager
Exec=MineGit
Icon=minegit
Categories=Game;Utility;
Terminal=false
EOF
cp "$APPDIR/minegit.desktop" "$APPDIR/usr/share/applications/minegit.desktop"

APPIMAGETOOL="$TOOLS_DIR/appimagetool-$APPIMAGE_ARCH.AppImage"
if [[ ! -f "$APPIMAGETOOL" ]]; then
  curl -L "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-$APPIMAGE_ARCH.AppImage" \
    -o "$APPIMAGETOOL"
fi
chmod +x "$APPIMAGETOOL"

OUTPUT_FILE="$DIST_DIR/${APP_NAME}-${APPIMAGE_ARCH}.AppImage"
ARCH="$APPIMAGE_ARCH" "$APPIMAGETOOL" --appimage-extract-and-run "$APPDIR" "$OUTPUT_FILE"

echo "AppImage created at: $OUTPUT_FILE"
