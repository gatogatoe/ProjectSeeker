# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import json
from pathlib import Path
import os
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app
import assistant_local
import mac_support


class MacTests(unittest.TestCase):
    def test_language_selection(self):
        for languages, expected in [('(it-CH,en-US)', 'it'), ('(fr-CH,en-US)', 'fr'), ('(de-CH)', 'de'), ('(en-US,it-IT)', 'en'), ('', 'en')]:
            with self.subTest(languages=languages), patch.object(mac_support.subprocess, 'run', return_value=SimpleNamespace(stdout=languages)):
                self.assertEqual(mac_support.sys_lang(), expected)

    def test_finder_arguments_preserve_special_names(self):
        path = '/Volumes/Music/Beat 日本語 & #1.flp'
        with patch.object(mac_support.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            mac_support.open_path(path)
            self.assertEqual(run.call_args.args[0], ['open', path])
        with patch.object(mac_support.subprocess, 'Popen') as popen:
            mac_support.reveal(path)
            self.assertEqual(popen.call_args.args[0], ['open', '-R', path])

    def test_search_folders_are_read_without_changing_fl_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            kit = Path(folder) / 'Kit 日本語'
            kit.mkdir()
            config = Path(folder) / 'reg.xml'
            text = '<Root><Key name="FL Studio 26"><Key name="Search paths"><Value value="&quot;' + str(kit) + '&quot;,"/></Key></Key></Root>'
            config.write_text(text, encoding='utf-8')
            with patch.object(mac_support.os.path, 'expanduser', side_effect=lambda value: str(config) if value.endswith('reg.xml') else value):
                self.assertEqual(mac_support.search_dirs(), [str(kit)])
            self.assertEqual(config.read_text(encoding='utf-8'), text)

    def test_missing_or_broken_fl_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'reg.xml'
            with patch.object(mac_support.os.path, 'expanduser', return_value=str(config)):
                self.assertEqual(mac_support.search_dirs(), [])
                config.write_text('<broken', encoding='utf-8')
                self.assertEqual(mac_support.search_dirs(), [])

    def test_mac_data_folder_and_windows_api_guards(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'MAC', True), patch.object(app, 'mac_support', mac_support, create=True), patch.object(app.os.path, 'expanduser', return_value=folder):
            self.assertEqual(app.data_dir(), os.path.join(folder, 'Library', 'Application Support', 'ProjectSeeker'))
            self.assertTrue(app.has_webview2())
            api = app.Api.__new__(app.Api)
            self.assertIsNone(api._install_window_frame())
            with self.assertRaisesRegex(OSError, 'macOS'):
                app.link_folder(folder)
            with self.assertRaisesRegex(OSError, 'macOS'):
                app.unlink_folder(folder)

    def test_synthetic_scan_handles_native_and_windows_sample_paths(self):
        sys.path.insert(0, str(Path(__file__).parent / 'test'))
        from make_edge_flp import body, ev, common, u16
        import struct
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'fl_search_dirs', return_value=[]), patch.object(app, '_fl_dirs', return_value={}):
            sample = Path(folder) / 'kick 日本語.wav'
            sample.write_bytes(b'audio')
            events = common('26.1.0.1', 140)
            for name in [str(sample), 'Z:\\Old PC\\kick 日本語.wav']:
                events += ev(64, struct.pack('<H', 0)) + ev(196, u16(name))
            project = Path(folder) / 'Test.flp'
            project.write_bytes(body(events + ev(99)))
            before = project.read_bytes()
            rows = app.scan_root(folder)
            self.assertEqual(len(rows), 1)
            self.assertTrue(all(s['e'] for s in rows[0]['samples']))
            self.assertIn('Z:\\Old PC\\kick 日本語.wav', [s['p'] for s in rows[0]['samples']])
            self.assertEqual(project.read_bytes(), before)

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires the native macOS Keychain')
    def test_native_keychain_save_endpoint_change_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            config = dict(url='https://example.invalid', model='test', key='synthetic-test-key')
            try:
                result = assistant_local.save_config(folder, config)
                self.assertTrue(result['has_key'])
                self.assertEqual(mac_support.read_key(folder), 'synthetic-test-key')
                self.assertFalse((Path(folder) / 'assistant.key').exists())
                self.assertNotIn('synthetic-test-key', (Path(folder) / 'assistant.keychain').read_text())
                self.assertNotIn('synthetic-test-key', json.dumps(result))
                result = assistant_local.save_config(folder, dict(config, url='https://other.invalid', key=''))
                self.assertFalse(result['has_key'])
                result = assistant_local.save_config(folder, config)
                self.assertTrue(result['has_key'])
                result = assistant_local.save_config(folder, dict(config, key='', clear_key=True))
                self.assertFalse(result['has_key'])
            finally:
                mac_support.save_key(folder, '')


if __name__ == '__main__':
    unittest.main()
