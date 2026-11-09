# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from contextlib import contextmanager

import app
import assistant_local

sys.path.insert(0, str(Path(__file__).parent / 'test'))
from make_edge_flp import body, ev


class DataRegressionTests(unittest.TestCase):
    def test_kit_file_stat_error_preserves_only_that_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            root = Path(folder) / 'Kits'
            root.mkdir()
            blocked = root / 'kick.wav'
            blocked.write_bytes(b'kick')
            removed = root / 'old.wav'
            removed.write_bytes(b'old')
            store = app.Store()
            store.scan_kits(str(root))
            removed.unlink()
            original = app.os.scandir
            def stat(entry):
                if entry.path == str(blocked):
                    raise PermissionError(13, 'denied', str(blocked))
                return entry.stat()
            @contextmanager
            def scandir(path):
                with original(path) as entries:
                    yield (SimpleNamespace(name=e.name, path=e.path, is_dir=e.is_dir, stat=lambda e=e: stat(e)) for e in entries)
            with patch.object(app.os, 'scandir', side_effect=scandir):
                store.scan_kits(str(root))
            lib = store.state['kitlib'][str(root)]
            self.assertEqual(lib['parts'][0]['files'], [['kick.wav', 4]])
            self.assertEqual(lib['inaccessible'], [str(blocked)])

    def test_partial_kit_scan_preserves_blocked_parts_and_updates_readable_files(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            root = Path(folder) / 'Kits 日本語'
            hidden = root / 'Pack' / 'Hidden'
            hidden.mkdir(parents=True)
            lost = hidden / 'kick.wav'
            lost.write_bytes(b'kick')
            visible = root / 'Pack' / 'old.wav'
            visible.write_bytes(b'old')
            store = app.Store()
            store.scan_kits(str(root))
            visible.unlink()
            (root / 'Pack' / 'new.wav').write_bytes(b'new sample')
            original = app.os.scandir
            def denied(path):
                if str(path) == str(hidden):
                    raise PermissionError(13, 'denied', str(hidden))
                return original(path)
            with patch.object(app.os, 'scandir', side_effect=denied):
                store.scan_kits(str(root))
            lib = store.state['kitlib'][str(root)]
            self.assertEqual(sorted(lib['parts'][0]['files']), sorted([['Hidden\\kick.wav', 4], ['new.wav', 10]]))
            self.assertEqual(lib['inaccessible'], [str(hidden)])
            self.assertEqual(app.Store().state['kitlib'][str(root)], lib)
            lost.unlink()
            store.scan_kits(str(root))
            self.assertEqual(store.state['kitlib'][str(root)]['inaccessible'], [])
            self.assertEqual(store.state['kitlib'][str(root)]['parts'][0]['files'], [['new.wav', 10]])

    def test_unreadable_kit_root_and_cancel_preserve_previous_index(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            root = Path(folder) / 'Kits'
            (root / 'Pack').mkdir(parents=True)
            (root / 'Pack' / 'kick.wav').write_bytes(b'kick')
            store = app.Store()
            store.scan_kits(str(root))
            parts = copy.deepcopy(store.state['kitlib'][str(root)]['parts'])
            with patch.object(app.os, 'scandir', side_effect=PermissionError(13, 'denied', str(root))):
                store.scan_kits(str(root))
            self.assertEqual(store.state['kitlib'][str(root)]['parts'], parts)
            self.assertEqual(store.state['kitlib'][str(root)]['inaccessible'], [str(root)])
            saved = Path(store.file).read_bytes()
            import threading
            cancel = threading.Event()
            with self.assertRaises(app.ScanCancelled):
                store.scan_kits(str(root), lambda *_: cancel.set(), cancel)
            self.assertEqual(Path(store.file).read_bytes(), saved)

    def test_invalid_assistant_config_cannot_crash_or_enable_sharing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'assistant.json'
            for value in (None, [], 42, 'text'):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding='utf-8')
                    self.assertEqual(assistant_local.read_config(folder)['url'], '')
            for sharing in ('false', 'true', [], 1, False, True):
                with self.subTest(sharing=sharing):
                    path.write_text(json.dumps({'url': 'https://provider.example/v1', 'model': 'test', 'share': sharing}), encoding='utf-8')
                    config = assistant_local.read_config(folder)
                    self.assertEqual(config['url'], 'https://provider.example/v1')
                    self.assertEqual(config['share'], sharing is True)
            path.write_text(json.dumps({'url': 'https://provider.example/v1', 'model': 'test', 'share': False}), encoding='utf-8-sig')
            self.assertEqual(assistant_local.read_config(folder)['url'], 'https://provider.example/v1')

    def test_store_round_trip_preserves_user_metadata_and_associations(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            root = str(Path(folder) / 'My beats 日本語')
            row = app._new_row(str(Path(root) / 'Città 🎵.flp'), root, root, 'Città 🎵')
            api = app.Api()
            api._store.state.update(paths=[root], projects=[row])
            api._store.save()
            api.set_prefs({'lang': 'fr', 'theme': 'light'})
            api.set_meta(row['path'], {'name': 'Été', 'tags': ['café', 'café', '日本語'], 'note': 'àè 🎵'})
            api.add_play(row['path'])
            api.add_play(row['path'])
            api.save_albums({'albums': [{'id': 'test1', 'name': 'Été', 'tracks': [row['path'], row['path'].upper()]}, {'id': 'test2', 'name': 'Second', 'tracks': [row['path']]}], 'playlists': [{'id': 'list1', 'name': 'Mix', 'tracks': [row['path']]}]})
            stored = app.Store()
            key = app.os.path.normcase(row['path'])
            self.assertEqual(stored.state['projects'], [row])
            self.assertEqual(stored.state['prefs']['lang'], 'fr')
            self.assertEqual(stored.meta[key], {'name': 'Été', 'tags': ['café', '日本語'], 'note': 'àè 🎵'})
            self.assertEqual(stored.plays[key]['n'], 2)
            self.assertEqual([a['tracks'] for a in stored.albums['albums']], [[key], []])
            self.assertEqual(stored.albums['playlists'][0]['tracks'], [key])

    def test_album_loader_ignores_malformed_entries_and_tracks(self):
        raw = {'albums': [{'id': []}, {'id': 'test1', 'cover': [], 'tracks': [None, {}, '', 123, 'C:\\beats\\a.flp']}], 'playlists': 42}
        got = app._clean_albums(raw, raw)
        self.assertEqual(got['albums'][0]['tracks'], [app.os.path.normcase('C:\\beats\\a.flp')])
        self.assertEqual(got['playlists'], [])

    def test_truncation_notice_follows_app_language(self):
        for language, expected in [('it', 'La risposta'), ('en', 'The response'), ('fr', 'La réponse'), ('de', 'Die Antwort')]:
            with self.subTest(language=language), tempfile.TemporaryDirectory() as folder:
                response = SimpleNamespace(status=200, read=lambda: b'{"choices":[{"message":{"content":"OK"},"finish_reason":"length"}]}')
                with patch.object(assistant_local, 'read_config', return_value=dict(url='http://127.0.0.1:1234/v1', model='test', local=True)), patch.object(assistant_local.urllib.request, 'build_opener') as opener:
                    opener.return_value.open.return_value.__enter__.return_value = response
                    answer = assistant_local.chat(folder, 'hello', [], '', language=language)
                self.assertIn('[' + expected, answer)

    def test_wrong_json_type_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'prefs.json'
            raw = '["recoverable"]'
            path.write_text(raw, encoding='utf-8')
            self.assertEqual(app._load_json(str(path), {}), {})
            app._save_json(str(path), {'theme': 'dark'})
            self.assertEqual([p.read_text(encoding='utf-8') for p in Path(folder).glob('prefs.rotto-*.json')], [raw])

    def test_json_bom_and_unicode_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'prefs.json'
            value = {'name': 'Città 日本語 🎵', 'path': 'C:\\My beats\\é.flp'}
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8-sig')
            self.assertEqual(app._load_json(str(path), {}), value)
            app._save_json(str(path), value)
            self.assertEqual(app._load_json(str(path), {}), value)

    def test_corrupt_json_backups_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'meta.json'
            with patch.object(app.datetime, 'datetime') as clock:
                clock.now.return_value.strftime.return_value = '20261108-120000'
                for raw in ('{"first"', '{"second"'):
                    path.write_text(raw, encoding='utf-8')
                    self.assertEqual(app._load_json(str(path), {}), {})
            self.assertEqual(sorted(p.read_text(encoding='utf-8') for p in Path(folder).glob('meta.rotto-*.json')), ['{"first"', '{"second"'])

    def test_cached_channels_are_isolated(self):
        row = app._new_row('C:\\beats\\a.flp', 'C:\\beats', 'C:\\beats', 'a')
        row['ch'] = [{'n': 0, 'pk': 'missing', 'pm': 1, 'sr': {'a': 'test.wav', 'm': ['test.wav']}}]
        original = copy.deepcopy(row)
        result = app._result_of(row)
        fresh = app._new_row(row['path'], row['root'], row['dir'], row['name'])
        app._read_project(fresh, result, {}, {}, {}, app._Exists(), set(), ('', ''), {})
        self.assertEqual(row, original)
        self.assertNotIn('pm', fresh['ch'][0])

    def test_unavailable_fl_sample_does_not_fail_project(self):
        with tempfile.TemporaryDirectory() as folder:
            sample = str(Path(folder) / 'kick.wav')
            with patch.object(app.os.path, 'getsize', side_effect=PermissionError('denied')):
                got, found = app._check_sample(sample, folder, app.os.path.normcase(folder), {}, {}, {}, type('Exists', (), {'file': lambda *_: True})())
            self.assertFalse(got['e'])
            self.assertIsNone(found)

    def test_unavailable_live_sample_does_not_fail_project(self):
        with tempfile.TemporaryDirectory() as folder:
            sample = str(Path(folder) / 'kick.wav')
            row = app._new_row(str(Path(folder) / 'a.als'), folder, folder, 'a')
            with patch.object(app.os.path, 'getsize', side_effect=FileNotFoundError('gone')):
                app._live_samples(row, [('3', 'kick.wav', sample)], type('Exists', (), {'file': lambda *_: True})())
            self.assertFalse(row['samples'][0]['e'])

    def test_legacy_tempo_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'old.flp'
            for bpm in (0, 65535, 140):
                with self.subTest(bpm=bpm):
                    path.write_bytes(body(ev(199, b'9.0.0.1\0') + ev(66, struct.pack('<H', bpm))))
                    got = app.parse_flp(str(path))
                    self.assertEqual(got['bpm'], 140 if bpm == 140 else None)
                    self.assertEqual('bpm' in got['warn'], bpm != 140)


if __name__ == '__main__':
    unittest.main()
