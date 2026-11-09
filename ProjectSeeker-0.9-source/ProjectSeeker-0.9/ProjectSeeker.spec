# -*- mode: python ; coding: utf-8 -*-
# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import os, re
from PyInstaller.utils.win32.versioninfo import (VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
                                                 StringStruct, VarFileInfo, VarStruct)

# Version shown in the exe's Properties > Details, taken from VERSION in app.py (code signing wants it in every build)
with open('app.py', encoding='utf-8') as f:
    VER = re.search(r"^VERSION = '([^']+)'", f.read(), re.M).group(1)
nums = tuple(([int(x) for x in VER.split('.')] + [0, 0, 0, 0])[:4])
info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=nums, prodvers=nums),
    kids=[StringFileInfo([StringTable('040904B0', [
        StringStruct('CompanyName', 'Project Seeker'),
        StringStruct('FileDescription', 'Project Seeker'),
        StringStruct('FileVersion', VER),
        StringStruct('InternalName', 'ProjectSeeker'),
        StringStruct('LegalCopyright', 'Copyright (C) 2026 Gato - GPL-3.0'),
        StringStruct('OriginalFilename', 'ProjectSeeker.exe'),
        StringStruct('ProductName', 'Project Seeker'),
        StringStruct('ProductVersion', VER)])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])])
os.makedirs('build', exist_ok=True)
with open(os.path.join('build', 'version_info.txt'), 'w', encoding='utf-8') as f:
    f.write(str(info))

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('ui', 'ui'), ('LICENSE', '.'), ('build/third-party/licenses', 'licenses'),
           ('build/third-party/THIRD_PARTY_NOTICES.md', '.')],
    hiddenimports=[],
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
    icon=['icona.ico'],
    version=os.path.join('build', 'version_info.txt'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ProjectSeeker',
)
