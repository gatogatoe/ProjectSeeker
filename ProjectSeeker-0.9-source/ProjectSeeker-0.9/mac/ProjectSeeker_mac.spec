# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import re

with open('app.py', encoding='utf-8') as stream:
    VER = re.search(r"^VERSION = '([^']+)'", stream.read(), re.M).group(1)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('ui', 'ui'), ('LICENSE', '.'), ('build/third-party/licenses', 'licenses'),
           ('build/third-party/THIRD_PARTY_NOTICES.md', '.')],
    hiddenimports=['keyring.backends.macOS'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
a.datas = [entry for entry in a.datas if not (entry[0].replace('\\', '/').startswith('ui/.test-') and entry[0].endswith('.html'))]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ProjectSeeker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name='ProjectSeeker')
app = BUNDLE(
    coll,
    name='Project Seeker.app',
    icon='icon_mac.png',
    bundle_identifier='io.github.projectseeker',
    version=VER,
    info_plist={
        'CFBundleName': 'Project Seeker',
        'CFBundleDisplayName': 'Project Seeker',
        'CFBundleShortVersionString': VER,
        'CFBundleVersion': VER,
        'NSHumanReadableCopyright': 'Copyright (C) 2026 Gato - GPL-3.0',
        'LSApplicationCategoryType': 'public.app-category.music',
        'LSMinimumSystemVersion': '11.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
    },
)
