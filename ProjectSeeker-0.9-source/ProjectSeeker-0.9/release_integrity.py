# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import argparse
import ast
import base64
import hashlib
import json
import importlib.metadata as metadata
import marshal
from pathlib import Path
import re
import sys
import types
import zlib

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def version():
    return re.search(r"^VERSION = '([^']+)'", (ROOT / 'app.py').read_text(encoding='utf-8'), re.M).group(1)


def require_license():
    if digest(ROOT / 'LICENSE') != '3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986':
        raise ValueError('LICENSE must be the unmodified official GNU GPL version 3 text')


def sources():
    names = ['app.py', 'assistant_local.py', 'assistant_library.py', 'LICENSE']
    names.extend(path.relative_to(ROOT).as_posix() for path in (ROOT / 'ui').rglob('*')
                 if path.is_file() and not path.name.startswith('.test-'))
    if (ROOT / 'mac_support.py').exists():
        names.append('mac_support.py')
    return {name: digest(ROOT / name) for name in sorted(names)}


def record(platform, package, bundle):
    require_license()
    from PyInstaller.archive.readers import CArchiveReader

    executable = bundle.parent / 'ProjectSeeker.exe' if platform == 'windows' else bundle.parent / 'MacOS' / 'ProjectSeeker'
    archive = CArchiveReader(str(executable))
    embedded = archive.open_embedded_archive('PYZ.pyz')

    def normalized(code):
        return code.replace(co_filename='', co_consts=tuple(normalized(value) if isinstance(value, types.CodeType) else value for value in code.co_consts))

    for name in ('app', 'assistant_local', 'assistant_library'):
        code = marshal.loads(archive.extract(name)) if name == 'app' else embedded.extract(name)
        expected = compile((ROOT / (name + '.py')).read_text(encoding='utf-8'), code.co_filename, 'exec')
        if normalized(code) != normalized(expected):
            raise ValueError('Packaged Python code differs from current source: ' + name)
    dependencies = json.loads((ROOT / 'build' / 'dependency-notices.json').read_text(encoding='utf-8'))
    mapping = metadata.packages_distributions()
    table = ast.literal_eval((ROOT / 'build' / 'ProjectSeeker' / 'PYZ-00.toc').read_text(encoding='utf-8'))
    for name, source, kind in table[1]:
        if 'site-packages' not in source:
            continue
        owners = mapping.get(name.split('.')[0], [])
        if not owners or any(owner.lower().replace('_', '-') not in dependencies['distributions'] for owner in owners):
            raise ValueError('Missing dependency license review for packaged module: ' + name)
    if digest(bundle / 'LICENSE') != digest(ROOT / 'LICENSE'):
        raise ValueError('Packaged application license differs from the approved license')
    notices = ROOT / 'build' / 'third-party'
    notice_hashes = {}
    for path in notices.rglob('*'):
        if path.is_file():
            relative = path.relative_to(notices).as_posix()
            if digest(bundle / relative) != digest(path):
                raise ValueError('Missing or altered packaged notice: ' + relative)
            notice_hashes[relative] = digest(path)
    if not notice_hashes:
        raise ValueError('Missing third-party notices')
    for path in (ROOT / 'ui').rglob('*'):
        if path.is_file() and not path.name.startswith('.test-'):
            if digest(bundle / 'ui' / path.relative_to(ROOT / 'ui')) != digest(path):
                raise ValueError('Packaged UI differs: ' + str(path))
    receipt = dict(version=version(), platform=platform, filename=package.name,
                   sha256=digest(package), license_sha256=digest(ROOT / 'LICENSE'),
                   sources=sources(), notices=notice_hashes)
    if (ROOT / 'SOURCE_SNAPSHOT.json').exists():
        receipt['main_sources'] = json.loads((ROOT / 'SOURCE_SNAPSHOT.json').read_text(encoding='utf-8'))['sha256']
    output = package.parent / (platform + '-receipt.json')
    output.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    package.with_name(package.name + '.sha256.txt').write_text(receipt['sha256'] + '  ' + package.name + '\n', encoding='ascii')
    print('RELEASE_RECEIPT=' + json.dumps(receipt, separators=(',', ':')))
    if platform.startswith('mac-'):
        payload = {name: base64.b64encode((notices / name).read_bytes()).decode('ascii') for name in notice_hashes}
        encoded = base64.b64encode(zlib.compress(json.dumps(payload).encode('utf-8'))).decode('ascii')
        chunks = [encoded[index:index + 24000] for index in range(0, len(encoded), 24000)]
        for index, chunk in enumerate(chunks, 1):
            print('RELEASE_NOTICES_PART=%d/%d:%s' % (index, len(chunks), chunk))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-license', action='store_true')
    parser.add_argument('--platform', choices=['windows', 'mac-arm64', 'mac-x86_64'])
    parser.add_argument('--package', type=Path)
    parser.add_argument('--bundle', type=Path)
    arguments = parser.parse_args()
    if arguments.check_license:
        require_license()
    elif arguments.platform and arguments.package and arguments.bundle:
        record(arguments.platform, arguments.package, arguments.bundle)
    else:
        parser.error('Provide --check-license or --platform, --package and --bundle')
