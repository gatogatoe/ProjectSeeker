# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import prepare_public
import release_integrity


class DistributionTests(unittest.TestCase):
    def test_documents_replace_stale_sources_and_preserve_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / 'public'
            (destination / '.git').mkdir(parents=True)
            (destination / '.git' / 'preserved').write_text('repository', encoding='utf-8')
            (destination / 'old-source.py').write_text('private', encoding='utf-8')
            (destination / 'old-copy').mkdir()
            (destination / 'old-copy' / 'notes.md').write_text('private notes', encoding='utf-8')
            with patch.object(prepare_public, 'PREVIEW', destination):
                prepare_public.prepare(stage=True, documents_only=True)
            self.assertEqual((destination / '.git' / 'preserved').read_text(), 'repository')
            self.assertFalse((destination / 'old-source.py').exists())
            self.assertFalse((destination / 'old-copy').exists())
            self.assertFalse(list(destination.rglob('*.py')))
            self.assertTrue((destination / 'LICENSE').exists())
            for line in (destination / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
                expected, name = line.split('  ', 1)
                self.assertEqual(release_integrity.digest(destination / name), expected)

    def test_license_must_match_unmodified_gnu_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'LICENSE').write_text('GPL with extra restrictions', encoding='utf-8')
            with patch.object(release_integrity, 'ROOT', root), self.assertRaises(ValueError):
                release_integrity.require_license()

    def test_corresponding_source_has_build_tools_and_excludes_private_material(self):
        data = prepare_public.source_archive()
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            names = {member.name.split('/', 1)[1] for member in archive.getmembers()}
            for name in ('app.py', 'LICENSE', 'build_release.py', 'build_mac.sh', 'prepare_mac.py',
                         'mac/app.py', 'mac/mac_support.py', 'mac/platform.patch', 'mac/ProjectSeeker_mac.spec'):
                self.assertIn(name, names)
            for name in names:
                self.assertNotIn('.git', Path(name).parts)
                self.assertNotIn('build', Path(name).parts)
                self.assertNotIn('dist', Path(name).parts)
                self.assertFalse(name.endswith(('NOTE_PROGETTO.md', 'prefs.json', 'libreria.json', 'assistant.key')))
                self.assertNotIn('fl26_1_template_image_line', name)
                self.assertNotIn('PROPOSED_LICENSE', name)


if __name__ == '__main__':
    unittest.main()
