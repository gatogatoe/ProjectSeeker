# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'build' / 'third-party'


def collect():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    queue = ['pywebview', 'setuptools', 'packaging', 'pyinstaller']
    if sys.platform == 'darwin':
        queue.extend(['keyring', 'pillow'])
    distributions = {}
    while queue:
        name = queue.pop()
        distribution = metadata.distribution(name)
        name = distribution.metadata['Name'].lower().replace('_', '-')
        if name in distributions:
            continue
        files = []
        for file in distribution.files or ():
            if not any(word in file.name.lower() for word in ('license', 'copying', 'notice', 'authors', 'copyright')):
                continue
            source = Path(distribution.locate_file(file))
            if not source.is_file() or source.suffix in ('.py', '.pyc', '.so', '.dll'):
                continue
            target = OUTPUT / 'licenses' / name / str(file).replace('../', '').replace('..\\', '')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files.append(target.relative_to(OUTPUT).as_posix())
        if not files and name != 'proxy-tools':
            raise ValueError('Missing complete license files for ' + name)
        distributions[name] = dict(version=distribution.version, licenses=files,
                                   license_expression=distribution.metadata.get('License-Expression'))
        for value in distribution.requires or ():
            requirement = Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                queue.append(requirement.name)
    upstream = json.loads((ROOT / 'licenses' / 'UPSTREAM_SOURCES.json').read_text(encoding='utf-8'))
    for name, evidence in upstream.items():
        path = ROOT / 'licenses' / 'upstream' / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence['sha256']:
            raise ValueError('Original upstream license has changed: ' + name)
        target = OUTPUT / 'licenses' / 'upstream' / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        target = OUTPUT / 'licenses' / 'Python' / 'LICENSE.txt'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(python_license, target)
    font = OUTPUT / 'licenses' / 'fonts' / 'OFL.txt'
    font.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'ui' / 'fonts' / 'OFL.txt', font)
    template = ROOT / 'release_docs' / 'THIRD_PARTY_NOTICES.md'
    if not template.exists():
        template = ROOT / 'THIRD_PARTY_NOTICES.md'
    shutil.copyfile(template, OUTPUT / 'THIRD_PARTY_NOTICES.md')
    inventory = '\n'.join('- %s %s' % (name, item['version']) for name, item in sorted(distributions.items()))
    with (OUTPUT / 'THIRD_PARTY_NOTICES.md').open('a', encoding='utf-8') as stream:
        stream.write('\n\n## Build dependency versions\n\n' + inventory + '\n')
    report = dict(python=sys.version, platform=sys.platform, distributions=distributions,
                  files={path.relative_to(OUTPUT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in OUTPUT.rglob('*') if path.is_file()})
    (ROOT / 'build' / 'dependency-notices.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Collected complete notices for %d distributions' % len(distributions))


if __name__ == '__main__':
    collect()
