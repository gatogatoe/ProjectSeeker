# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

from release_integrity import digest, require_license, sources, version

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT.parent / 'ProjectSeeker-pubblico'
PREVIEW = ROOT / 'build' / 'public-preview'
SOURCE_FILES = (
    'app.py', 'assistant_local.py', 'assistant_library.py', 'LICENSE', 'README.md',
    'requirements.txt', 'ProjectSeeker.spec', 'installer.iss', 'icona.ico', 'DISTRIBUTION.md', 'github_build.yml',
    'build.bat', 'build_mac.sh', 'build_release.py', 'prepare_mac.py',
    'prepare_public.py', 'collect_notices.py', 'release_integrity.py',
    'test_reader.py', 'test_scan.py', 'test_debug.py', 'test_assistant.py',
    'test_data_ui.js', 'test_assistant_controls.js', 'test_filters_ui.py',
    'test_pages_ui.py', 'test_release_ui.py', 'test_assistant_ui.py', 'test_distribution.py',
)
MAC_FILES = (
    'app.py', 'assistant_local.py', 'assistant_library.py', 'mac_support.py',
    'LICENSE', 'README.md', 'MAC_GUIDE.md', 'requirements_mac.txt',
    'ProjectSeeker_mac.spec', 'icon_mac.png', 'build_mac.sh', 'start_mac.command',
    'platform.patch', 'collect_notices.py', 'release_integrity.py',
    '.github/workflows/build_mac.yml', '.gitattributes', '.gitignore',
    'THIRD_PARTY_NOTICES.md', 'test_mac.py', 'test_mac_ui.js',
    'test_reader.py', 'test_scan.py', 'test_debug.py', 'test_assistant.py',
    'test_data_ui.js', 'test_assistant_controls.js',
)


def source_files():
    names = list(SOURCE_FILES) + ['mac/' + name for name in MAC_FILES]
    for folder in ('ui', 'test', 'mac/ui', 'mac/test', 'licenses', 'mac/licenses', 'release_docs', 'docs'):
        names.extend(path.relative_to(ROOT).as_posix() for path in (ROOT / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and not path.name.startswith(('.test-', 'fl26_1_template_image_line.'))
                     and path.suffix != '.pyc')
    return sorted(set(names))


def source_archive():
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz', format=tarfile.PAX_FORMAT) as archive:
        for name in source_files():
            path = ROOT / name
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError('Unsafe source path: ' + name)
            data = path.read_bytes()
            item = tarfile.TarInfo('ProjectSeeker-' + version() + '/' + name)
            item.size = len(data)
            item.mode = 0o755 if path.suffix in ('.sh', '.command') else 0o644
            archive.addfile(item, io.BytesIO(data))
    return output.getvalue()


def packages(windows_only=False):
    require_license()
    result = {}
    for platform, relative in (
        ('windows', 'dist/ProjectSeeker-setup-' + version() + '.exe'),
        ('mac-arm64', 'dist/mac/ProjectSeeker-' + version() + '-mac-arm64.dmg'),
        ('mac-x86_64', 'dist/mac/ProjectSeeker-' + version() + '-mac-x86_64.dmg'),
    ):
        if windows_only and platform != 'windows':
            continue
        package = ROOT / relative
        receipt = json.loads((package.parent / (platform + '-receipt.json')).read_text(encoding='utf-8'))
        if (receipt['filename'] != package.name or receipt['version'] != version()
                or receipt['sha256'] != digest(package) or receipt['license_sha256'] != digest(ROOT / 'LICENSE')):
            raise ValueError('Stale or inconsistent package: ' + platform)
        expected_sources = sources() if platform == 'windows' else json.loads((ROOT / 'mac' / 'SOURCE_SNAPSHOT.json').read_text(encoding='utf-8'))['sha256']
        if platform == 'windows' and receipt['sources'] != expected_sources:
            raise ValueError('Windows package does not match current sources')
        if platform != 'windows':
            if receipt['main_sources'] != expected_sources:
                raise ValueError('Mac package does not match current main sources')
            for name, expected in expected_sources.items():
                if digest(ROOT / name) != expected:
                    raise ValueError('Main sources changed since Mac synchronization: ' + name)
            for name, expected in receipt['sources'].items():
                if digest(ROOT / 'mac' / name) != expected:
                    raise ValueError('Mac sources changed after packaging: ' + name)
        result[package.name] = package.read_bytes()
        notice_root = ROOT / 'dist' / 'release-notices' / platform
        for name, expected in receipt['notices'].items():
            path = notice_root / name
            if digest(path) != expected:
                raise ValueError('Missing original notice: ' + platform + '/' + name)
            if name == 'THIRD_PARTY_NOTICES.md':
                result['docs/' + platform.upper() + '_COMPONENTS.md'] = path.read_bytes()
            else:
                result['licenses/' + platform + '/' + name.removeprefix('licenses/')] = path.read_bytes()
    return result


def prepare(stage=False, documents_only=False, windows_only=False):
    destination = PREVIEW if stage else PUBLIC
    if destination.is_symlink() or (destination.exists() and destination.is_junction()):
        raise ValueError('Publication destination must not be a link or junction')
    destination = destination.resolve()
    if destination not in (PUBLIC.absolute(), PREVIEW.absolute()) or destination == ROOT:
        raise ValueError('Unexpected publication destination')
    require_license()
    expected = {'LICENSE': (ROOT / 'LICENSE').read_bytes()}
    for name in ('README.md', 'MAC_GUIDE.md', 'ASSISTANT.md', 'THIRD_PARTY_NOTICES.md'):
        expected['README.md' if name == 'README.md' else 'docs/' + name] = (ROOT / 'release_docs' / name).read_bytes()
    downloads = ('- Windows 10/11, 64-bit: run `ProjectSeeker-setup-@VERSION@.exe`. Microsoft Edge WebView2 Runtime is required. The installer works without administrator rights.\n'
                 + ('\nmacOS packages are still being prepared and are not included in this distribution.\n' if windows_only else
                    '- Apple Silicon: open `ProjectSeeker-@VERSION@-mac-arm64.dmg` and drag the app to Applications.\n- Intel Mac: use `ProjectSeeker-@VERSION@-mac-x86_64.dmg`.\n'))
    expected['README.md'] = expected['README.md'].replace(b'@DOWNLOADS@', downloads.encode('utf-8')).replace(b'@VERSION@', version().encode('ascii'))
    expected['docs/DEPENDENCY_LICENSES.md'] = (ROOT / 'docs' / 'DEPENDENCY_LICENSES.md').read_bytes()
    expected['docs/GETTING_STARTED.md'] = (ROOT / 'docs' / 'GETTING_STARTED.md').read_bytes().replace(b'../ASSISTENTE.md', b'ASSISTANT.md')
    expected['docs/SEARCH_FILTER.md'] = (ROOT / 'SEARCH_FILTER.md').read_bytes()
    for path in (ROOT / 'docs' / 'screenshots').glob('*.png'):
        expected[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    if documents_only:
        expected['README.md'] = b'> Release preparation in progress. Packages have not been validated for this license yet.\n\n' + expected['README.md']
        for path in (ROOT / 'licenses' / 'upstream').iterdir():
            if path.is_file():
                expected['licenses/upstream/' + path.name] = path.read_bytes()
    else:
        expected.update(packages(windows_only))
        expected['ProjectSeeker-' + version() + '-source.tar.gz'] = source_archive()
    checksum = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n' for name, data in sorted(expected.items()))
    expected['SHA256SUMS.txt'] = checksum.encode('utf-8')
    destination.mkdir(parents=True, exist_ok=True)
    existing = [path for path in destination.rglob('*') if '.git' not in path.relative_to(destination).parts]
    for path in existing:
        if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(destination):
            raise ValueError('Unsafe publication path: ' + str(path))
    for path in sorted(existing, key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    for name, content in expected.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    actual = {path.relative_to(destination).as_posix(): digest(path) for path in destination.rglob('*')
              if path.is_file() and '.git' not in path.relative_to(destination).parts}
    wanted = {name: hashlib.sha256(data).hexdigest() for name, data in expected.items()}
    if actual != wanted:
        raise ValueError('Publication contents differ from the explicit allowlist')
    manifest = ROOT / 'build' / ('public-preview-manifest.json' if stage else 'public-manifest.json')
    manifest.write_text(json.dumps(dict(destination=str(destination), documents_only=documents_only, windows_only=windows_only, files=actual), indent=2), encoding='utf-8')
    print('Prepared %d public files in %s' % (len(actual), destination))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', action='store_true')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--documents-only', action='store_true')
    mode.add_argument('--windows-only', action='store_true')
    arguments = parser.parse_args()
    prepare(arguments.stage, arguments.documents_only, arguments.windows_only)
