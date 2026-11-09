# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import os
from pathlib import Path
import shutil
import subprocess
import sys

from release_integrity import record, require_license, version

ROOT = Path(__file__).resolve().parent


def run(*arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def build():
    require_license()
    run(sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt')
    run(sys.executable, 'collect_notices.py')
    run(sys.executable, '-m', 'py_compile', 'app.py', 'assistant_local.py', 'assistant_library.py')
    run(sys.executable, 'test_reader.py')
    run(sys.executable, 'test_scan.py')
    run(sys.executable, '-m', 'unittest', 'test_debug', 'test_assistant', 'test_distribution')
    run('node', '--test', 'test_data_ui.js')
    run('node', 'test_assistant_controls.js')
    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', 'ProjectSeeker.spec')
    candidates = [Path(os.environ.get(name, '')) / 'Inno Setup 6' / 'ISCC.exe'
                  for name in ('ProgramFiles(x86)', 'ProgramFiles')]
    candidates.append(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Inno Setup 6' / 'ISCC.exe')
    compiler = next((path for path in candidates if path.is_file()), None)
    if compiler is None:
        raise FileNotFoundError('Inno Setup 6 is required to build the installer')
    run(str(compiler), '/DAppVersion=' + version(), 'installer.iss')
    record('windows', ROOT / 'dist' / ('ProjectSeeker-setup-' + version() + '.exe'),
           ROOT / 'dist' / 'ProjectSeeker' / '_internal')
    target = ROOT / 'dist' / 'release-notices' / 'windows'
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ROOT / 'build' / 'third-party', target)
    print('Windows installer and original notices verified. Installation has not been tested.')


if __name__ == '__main__':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    build()
