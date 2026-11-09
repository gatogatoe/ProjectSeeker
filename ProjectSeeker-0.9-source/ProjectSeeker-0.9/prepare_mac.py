# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
MAC = ROOT / 'mac'
SHARED = (
    'app.py', 'assistant_local.py', 'assistant_library.py', 'LICENSE',
    'test_reader.py', 'test_scan.py', 'test_debug.py', 'test_assistant.py',
    'test_data_ui.js', 'test_assistant_controls.js',
)


def prepare():
    files = list(SHARED)
    for folder in ('ui', 'test'):
        files.extend(path.relative_to(ROOT).as_posix() for path in (ROOT / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and not path.name.startswith(('.test-', 'fl26_1_template_image_line.'))
                     and path.suffix != '.pyc')
    original = {name: (ROOT / name).read_bytes() for name in files}
    with tempfile.TemporaryDirectory(prefix='mac-sync-', dir=ROOT / 'build') as temporary:
        stage = Path(temporary)
        for name, content in original.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        subprocess.run(['git', 'apply', '--check', str(MAC / 'platform.patch')], cwd=stage, check=True)
        subprocess.run(['git', 'apply', str(MAC / 'platform.patch')], cwd=stage, check=True)
        for name in files:
            target = MAC / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix == '.json' and target.exists():
                if json.loads(target.read_text(encoding='utf-8')) == json.loads((stage / name).read_text(encoding='utf-8')):
                    continue
            shutil.copyfile(stage / name, target)
    for name in ('collect_notices.py', 'release_integrity.py'):
        if (ROOT / name).exists():
            shutil.copyfile(ROOT / name, MAC / name)
    if (ROOT / 'licenses').exists():
        shutil.copytree(ROOT / 'licenses', MAC / 'licenses', dirs_exist_ok=True)
    for name in ('THIRD_PARTY_NOTICES.md', 'MAC_GUIDE.md'):
        if (ROOT / 'release_docs' / name).exists():
            shutil.copyfile(ROOT / 'release_docs' / name, MAC / name)
    manifest = dict(prepared_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_edition='Main private development folder with explicit macOS adaptations',
                    sha256={name: hashlib.sha256(data).hexdigest() for name, data in original.items()})
    (MAC / 'SOURCE_SNAPSHOT.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Prepared %d shared Mac files; Windows sources unchanged' % len(files))


if __name__ == '__main__':
    (ROOT / 'build').mkdir(exist_ok=True)
    prepare()
