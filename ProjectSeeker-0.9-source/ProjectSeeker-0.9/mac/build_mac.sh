#!/bin/bash
# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
set -euo pipefail
cd "$(dirname "$0")"
exec > >(tee build_mac_log.txt) 2>&1

PY=${PYTHON:-python3}
"$PY" release_integrity.py --check-license
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements_mac.txt

ARCH=$(uname -m)
if [ -n "${EXPECTED_ARCH:-}" ] && [ "$ARCH" != "$EXPECTED_ARCH" ]; then
    echo "Expected $EXPECTED_ARCH, got $ARCH"
    exit 1
fi
python -c "import platform; assert platform.machine() == '$ARCH', platform.machine()"
python -m py_compile app.py assistant_local.py assistant_library.py mac_support.py
python test_reader.py
python -m unittest test_debug test_assistant test_mac
node --test test_data_ui.js test_mac_ui.js
node test_assistant_controls.js

python collect_notices.py
python -m PyInstaller --noconfirm --clean ProjectSeeker_mac.spec

VER=$(sed -n "s/^VERSION = '\(.*\)'/\1/p" app.py)
DMG="dist/ProjectSeeker-$VER-mac-$ARCH.dmg"
file "dist/Project Seeker.app/Contents/MacOS/ProjectSeeker"
test "$(lipo -archs 'dist/Project Seeker.app/Contents/MacOS/ProjectSeeker')" = "$ARCH"
codesign --verify --deep --strict --verbose=2 "dist/Project Seeker.app"
python -m pip freeze > "dist/dependencies-$ARCH.txt"

"dist/Project Seeker.app/Contents/MacOS/ProjectSeeker" --mac-build-check "dist/smoke-$ARCH.json" &
SMOKE_PID=$!
for attempt in $(seq 1 120); do
    if ! kill -0 "$SMOKE_PID" 2>/dev/null; then
        break
    fi
    sleep 1
done
if kill -0 "$SMOKE_PID" 2>/dev/null; then
    kill "$SMOKE_PID"
    echo 'Packaged app smoke test timed out'
    exit 1
fi
wait "$SMOKE_PID"
python -c "import json; r=json.load(open('dist/smoke-$ARCH.json')); print(r); assert r['ok'] and r['arch']=='$ARCH'"

mkdir -p build/dmg
ditto "dist/Project Seeker.app" "build/dmg/Project Seeker.app"
ln -sfn /Applications build/dmg/Applications
cp MAC_GUIDE.md LICENSE build/dmg/
cp build/third-party/THIRD_PARTY_NOTICES.md build/dmg/
ditto build/third-party/licenses build/dmg/licenses
hdiutil create -volname 'Project Seeker' -srcfolder build/dmg -ov -format UDZO "$DMG"
hdiutil verify "$DMG"
mkdir -p build/verify-dmg
hdiutil attach "$DMG" -readonly -nobrowse -mountpoint "$PWD/build/verify-dmg"
trap 'hdiutil detach "$PWD/build/verify-dmg"' EXIT
cmp LICENSE build/verify-dmg/LICENSE
python release_integrity.py --platform "mac-$ARCH" --package "$DMG" --bundle "build/verify-dmg/Project Seeker.app/Contents/Resources"
hdiutil detach "$PWD/build/verify-dmg"
trap - EXIT
mkdir -p "dist/release-notices/mac-$ARCH"
ditto build/third-party "dist/release-notices/mac-$ARCH"
(cd dist && shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256.txt")
echo "Done: $DMG"
cat "$DMG.sha256.txt"
