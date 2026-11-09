# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app
import assistant_library as library
import assistant_local


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.raw = [dict(path='C:\\beats\\a.flp', name='Notte', daw='FL Studio', bpm=140, hours=20,
                         modified='2024-02-01', created='2023-01-01', native=['Flex'], vst=['Serum']),
                    dict(path='C:\\beats\\b.als', name='Alba', daw='Ableton Live', bpm=140, hours=900,
                         modified='2026-10-01', native=[], vst=['Serum']),
                    dict(path='C:\\beats\\c.flp', name='Senza dati', native=[], vst=[])]
        self.meta = {os.path.normcase(self.raw[0]['path']): dict(name='Nuit', tags=['Trap'], note='melodia scura')}
        self.plays = {os.path.normcase(self.raw[0]['path']): dict(n=4, t='2026-11-01T10:00:00Z'),
                      'removed.flp': dict(n=100)}
        self.rows = library.projects(self.raw, self.meta, self.plays)

    def plan(self, **values):
        return library.parse_plan(json.dumps(dict(intent='search', **values)))

    def test_combined_filters(self):
        result = library.search(self.rows, self.plan(bpm_min=140, bpm_max=140, plugins=['serum'], tags=['trap']))
        self.assertEqual([p['name'] for p in result], ['Nuit'])
        self.assertEqual(library.search(self.rows, self.plan(bpm_min=141, plugins=['Serum'])), [])
        self.assertEqual(library.search(self.rows, self.plan(tags=['rap'])), [])

    def test_names_notes_and_dates(self):
        for text in ('nuit', 'notte', 'scura'):
            self.assertEqual(len(library.search(self.rows, self.plan(text=[text]))), 1)
        result = library.search(self.rows, self.plan(created_after='2023-01-01', modified_before='2024-02-01', hours_min=20))
        self.assertEqual(len(result), 1)
        self.assertEqual(library.search(self.rows, self.plan(hours_min=21)), [])

    def test_unknowns_and_ordering(self):
        result = library.search(self.rows, self.plan(sort='idle_hours'))
        self.assertEqual([p['name'] for p in result], ['Nuit'])
        self.assertEqual(library.search(self.rows, self.plan(sort='modified_asc'))[-1]['name'], 'Senza dati')
        self.assertIsNone(self.rows[1]['hours'])

    def test_summary_is_cumulative_and_library_scoped(self):
        stats = library.summary(self.rows)
        self.assertEqual(stats['in_app_plays'], 4)
        self.assertEqual(stats['played_projects'], 1)
        self.assertEqual(stats['fl_reported_hours'], 20)
        self.assertEqual(stats['projects_with_fl_hours'], 1)
        self.assertIn('not annual', stats['scope'])
        self.assertEqual(library.summary([])['top_played'], [])
        self.assertEqual(len(library.projects(self.raw + self.raw, self.meta, self.plays)), 3)

    def test_invalid_plans(self):
        for raw in ('{}', '[]', 'not JSON', '{"intent":"delete"}', '{"intent":"search","bpm_min":true}',
                    '{"intent":"search","hours_min":-1}', '{"intent":"search","tags":"trap"}',
                    '{"intent":"search","sort":"execute"}', '{"intent":"search","created_after":"yesterday"}',
                    '{"intent":"search","bpm_min":150,"bpm_max":140}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                library.parse_plan(raw)

    def test_wrapped_period_filters_and_missing_history(self):
        period = dict(start='2023-01-01', end='2023-12-31', field='created')
        stats = library.summary(self.rows, period)
        self.assertEqual(stats['projects'], 1)
        self.assertEqual(stats['fl_reported_hours'], 20)
        self.assertIsNone(stats['in_app_plays'])
        self.assertEqual(stats['top_played'], [])
        self.assertEqual(stats['period'], period)
        self.assertEqual(library.summary(self.rows, dict(period, field='modified'))['projects'], 0)
        self.assertEqual(library.summary(self.rows, dict(period, start='2024-02-01', end='2024-02-01', field='modified'))['projects'], 1)
        for value in ('2024', [], dict(period, start='2023-02-29'), dict(period, end='2022-12-31'), dict(period, field='plays'), dict(start='2023-01-01')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                library.summary(self.rows, value)

    def test_wrapped_types_and_real_name_highlights(self):
        period = dict(start='2026-01-01', end='2026-12-31', field='modified')
        projects = library.summary(self.rows, period, 'projects')
        self.assertEqual(projects['projects'], 1)
        self.assertIsNone(projects['in_app_plays'])
        self.assertNotIn('listening', projects)
        self.assertEqual(projects['name_highlights']['longest']['name'], 'Alba')
        listening = library.summary(self.rows, period, 'listening')
        self.assertNotIn('period', listening)
        self.assertEqual(listening['projects'], 1)
        self.assertEqual(listening['listening']['in_app_plays'], 4)
        self.assertIsNone(listening['fl_reported_hours'])
        self.assertEqual(listening['top_hours'], [])
        self.assertEqual(listening['name_highlights']['longest'], dict(name='Nuit', characters=4))
        both = library.summary(self.rows, period, 'both')
        self.assertEqual(both['projects'], 1)
        self.assertEqual(both['period'], period)
        self.assertEqual(both['listening']['in_app_plays'], 4)
        self.assertEqual(both['listening']['top_played'][0]['name'], 'Nuit')
        self.assertEqual(library.summary([], kind='listening')['name_highlights']['candidates'], [])
        self.assertIsNone(library.summary([], kind='projects')['name_highlights']['longest'])
        named = [dict(self.rows[0], name='x<script>😀', path='long'), dict(self.rows[1], name='ab', path='short')]
        names = library.summary(named, kind='projects')['name_highlights']
        self.assertEqual(names['longest'], dict(name='x<script>😀', characters=10))
        self.assertEqual(set(names['candidates']), {'x<script>😀', 'ab'})
        with self.assertRaises(ValueError):
            library.summary(self.rows, kind='invalid')

    def test_context_is_resolved_from_library_and_limited(self):
        selected = self.raw[0]['path'].upper() if os.name == 'nt' else self.raw[0]['path']
        data, cards = library.context(self.rows, self.plan(), selected)
        self.assertEqual(json.loads(data)['selected_project']['note'], 'melodia scura')
        data, _ = library.context(self.rows, self.plan(), 'C:\\invented.flp')
        self.assertIsNone(json.loads(data)['selected_project'])
        data, cards = library.context(self.rows * 10, self.plan())
        self.assertEqual(json.loads(data)['result_count'], 30)
        self.assertEqual(len(cards), 12)


class TransportTests(unittest.TestCase):
    def test_app_language_in_payload_for_greetings_and_wrapped(self):
        for language, expected in (('it', 'Italian'), ('en', 'English'), ('de', 'German'), ('fr', 'French')):
            for task, message in (('chat', 'hi'), ('wrapped', 'Give me my Wrapped')):
                with self.subTest(language=language, task=task), tempfile.TemporaryDirectory() as folder:
                    config = dict(url='http://127.0.0.1:1234/v1', model='test', local=True, share=True)
                    response = SimpleNamespace(status=200, read=lambda: b'{"choices":[{"message":{"content":"OK"}}]}')
                    opener = unittest.mock.MagicMock()
                    opener.open.return_value.__enter__.return_value = response
                    with patch.object(assistant_local, 'read_config', return_value=config), patch.object(assistant_local.urllib.request, 'build_opener', return_value=opener):
                        assistant_local.chat(folder, message, [dict(role='assistant', content='Vecchia risposta italiana')], '', task=task, language=language)
                    payload = json.loads(opener.open.call_args.args[0].data)
                    self.assertIn('Response language: ' + expected, payload['messages'][0]['content'])
                    self.assertEqual(payload['messages'][-1]['content'], message)
        with self.assertRaises(ValueError):
            assistant_local.system_prompt('chat', 'unsupported')

    def test_api_language_for_all_modes_and_privacy(self):
        api = app.Api.__new__(app.Api)
        api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=[]), meta={}, plays={})
        for task in ('', 'search', 'inspiration', 'wrapped'):
            for shared in (True, False):
                with self.subTest(task=task, shared=shared), tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
                    with patch.object(assistant_local, 'read_config', return_value=dict(local=False, share=shared)), patch.object(assistant_local, 'chat', side_effect=['{"intent":"search"}', 'OK'] if task == 'search' and shared else ['OK']) as chat:
                        result = api.assistant_chat('hi', task=task, language='en')
                    self.assertTrue(result['ok'])
                    self.assertEqual(chat.call_args.kwargs['language'], 'en')

    def test_plain_chat_skips_library_and_planning(self):
        api = app.Api.__new__(app.Api)
        api._store = SimpleNamespace(lock=threading.RLock())
        history = [dict(role='user', content='Earlier')]
        for local, shared in ((True, True), (False, True), (False, False)):
            with self.subTest(local=local, shared=shared), tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
                with patch.object(assistant_local, 'read_config', return_value=dict(local=local, share=shared)), patch.object(assistant_local, 'chat', return_value='Ciao!') as chat, patch.object(library, 'projects', side_effect=AssertionError('No library access')), patch.object(library, 'parse_plan', side_effect=AssertionError('No planning')):
                    result = api.assistant_chat('ciao', history, 'selected-project', 'normal-request')
                self.assertTrue(result['ok'])
                self.assertEqual(result['answer'], 'Ciao!')
                self.assertEqual(result['projects'], [])
                chat.assert_called_once()
                self.assertEqual(chat.call_args.args, (folder, 'ciao', history if local or shared else [], ''))
                self.assertNotIn('instruction', chat.call_args.kwargs)
                self.assertEqual(api.assistant_status('normal-request')['stage'], 'answer')

    def test_create_skips_planning_and_uses_only_selected_project(self):
        api = app.Api.__new__(app.Api)
        project = dict(path='C:\\beats\\a.flp', name='A', native=[], vst=['Serum'])
        api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=[project]), meta={}, plays={})
        for selected in ('', project['path']):
            with self.subTest(selected=selected), tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
                with patch.object(assistant_local, 'read_config', return_value=dict(local=True)), patch.object(assistant_local, 'chat', return_value='Idea') as chat:
                    result = api.assistant_chat('Dammi un titolo', [], selected, task='inspiration')
                self.assertTrue(result['ok'])
                chat.assert_called_once()
                self.assertEqual(chat.call_args.kwargs['task'], 'inspiration')
                context = json.loads(chat.call_args.args[3])
                self.assertEqual(set(context), {'selected_project'})
                self.assertEqual(context['selected_project']['path'] if selected else context['selected_project'], selected or None)

    def test_plain_payload_preserves_message_and_disabled_reasoning(self):
        with tempfile.TemporaryDirectory() as folder:
            config = dict(url='http://127.0.0.1:1234/v1', model='qwen', local=True, share=True, reasoning='none')
            response = SimpleNamespace(status=200, read=lambda: b'{"choices":[{"message":{"content":"Ciao!"}}]}')
            opener = unittest.mock.MagicMock()
            opener.open.return_value.__enter__.return_value = response
            with patch.object(assistant_local, 'read_config', return_value=config), patch.object(assistant_local.urllib.request, 'build_opener', return_value=opener):
                self.assertEqual(assistant_local.chat(folder, 'ciao', [], ''), 'Ciao!')
            payload = json.loads(opener.open.call_args.args[0].data)
            self.assertEqual(payload['reasoning_effort'], 'none')
            self.assertEqual(payload['messages'], [dict(role='system', content=assistant_local.system_prompt('chat')), dict(role='user', content='ciao')])
            self.assertNotIn('Project Seeker', payload['messages'][0]['content'])

    def test_payload_privacy_reasoning_and_no_output_limit(self):
        for shared in (False, True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory() as folder:
                config = dict(url='https://provider.example/v1', model='test', local=False, share=shared, reasoning='high')
                response = SimpleNamespace(status=200, read=lambda: b'{"choices":[{"message":{"content":"<think>hidden</think>ok"}}]}')
                opener = unittest.mock.MagicMock()
                opener.open.return_value.__enter__.return_value = response
                with patch.object(assistant_local, 'read_config', return_value=config), patch.object(assistant_local.urllib.request, 'build_opener', return_value=opener):
                    answer = assistant_local.chat(folder, 'hello', [dict(role='assistant', content='PRIVATE_OLD')], 'PRIVATE_LIBRARY')
                payload = json.loads(opener.open.call_args.args[0].data)
                serialized = json.dumps(payload)
                self.assertEqual(answer, 'ok')
                self.assertEqual('PRIVATE_LIBRARY' in serialized, shared)
                self.assertEqual('PRIVATE_OLD' in serialized, shared)
                self.assertEqual(payload['reasoning_effort'], 'high')
                self.assertNotIn('max_tokens', payload)
                self.assertNotIn('max_completion_tokens', payload)
                self.assertNotIn('audio', payload)

    def test_streaming_hides_reasoning_and_detects_truncation(self):
        events = [dict(choices=[dict(delta=dict(content=c))]) for c in ('<thi', 'nk>secret', '</think>Ciao', ' mondo')]
        lines = [('data: ' + json.dumps(e) + '\n').encode() for e in events] + [b'data: [DONE]\n']
        updates = []
        result = assistant_local.stream_response(lines, lambda text, reasoning: updates.append((text, reasoning)))
        self.assertEqual(updates[-1][0], 'Ciao mondo')
        self.assertFalse(any('secret' in text or '<thi' in text for text, _ in updates))
        self.assertIn(True, [reasoning for _, reasoning in updates])
        with self.assertRaises(ValueError):
            assistant_local.stream_response(lines[:-1], lambda *_: None)
        self.assertIn('secret', result['message']['content'])

    def test_shared_profile_adds_only_current_task(self):
        for task in ('search', 'wrapped', 'inspiration'):
            prompt = assistant_local.system_prompt(task)
            self.assertIn(assistant_local.BASE_PROMPT, prompt)
            self.assertIn(assistant_local.TASK_PROMPTS[task], prompt)
            for other in assistant_local.TASK_PROMPTS:
                if other != task:
                    self.assertNotIn(assistant_local.TASK_PROMPTS[other], prompt)
        self.assertEqual(assistant_local.system_prompt('unknown'), assistant_local.system_prompt('chat'))
        self.assertNotIn(assistant_local.BASE_PROMPT, assistant_local.system_prompt('chat'))
        data, _ = library.context([], library.parse_plan('{"intent":"wrapped"}'))
        wrapped = json.loads(data)
        self.assertIn('summary', wrapped)
        self.assertNotIn('result_count', wrapped)
        self.assertNotIn('query', wrapped)
        data, _ = library.context([], library.parse_plan('{"intent":"inspiration"}'))
        self.assertNotIn('summary', json.loads(data))

    def test_endpoint_security(self):
        for url in ('http://remote.example', 'https://user:secret@example.com', 'https://example.com/v1?key=secret'):
            with self.assertRaises(ValueError):
                assistant_local.endpoint(url)
        self.assertTrue(assistant_local.endpoint('http://127.0.0.1:1234/v1')[1])

    def test_api_queries_and_context_persistence(self):
        api = app.Api.__new__(app.Api)
        project = dict(path='C:\\beats\\a.flp', name='A', native=[], vst=['Serum'], bpm=140)
        api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=[project]), meta={}, plays={})
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            with patch.object(assistant_local, 'read_config', return_value=dict(local=True)), patch.object(assistant_local, 'chat', side_effect=['{"intent":"search","plugins":["Serum"]}', 'Found']):
                result = api.assistant_chat('find Serum', [], project['path'], task='search')
            self.assertTrue(result['ok'])
            self.assertEqual(result['projects'][0]['path'], project['path'])
            saved = api.assistant_chat_save('', [dict(role='user', content='titles?', project_context=project['path'], mode='inspiration')])
            self.assertTrue(saved['ok'])
            self.assertEqual(api.assistant_chats()[0]['messages'][0]['project_context'], project['path'])
            self.assertEqual(api.assistant_chats()[0]['messages'][0]['mode'], 'inspiration')
            with patch.object(assistant_local, 'read_config', return_value=dict(local=False, share=False)), patch.object(assistant_local, 'chat', return_value='No library access') as chat:
                result = api.assistant_chat('wrapped', [dict(role='assistant', content='PRIVATE')], project['path'])
            self.assertTrue(result['ok'])
            self.assertEqual(chat.call_args.args[2:], ([], ''))
            self.assertEqual(result['projects'], [])

    def test_wrapped_shortcut_skips_planning_and_respects_privacy(self):
        api = app.Api.__new__(app.Api)
        project = dict(path='C:\\beats\\a.flp', name='A', native=[], vst=[], hours=2)
        api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=[project]), meta={}, plays={})
        for shared in (False, True):
            with self.subTest(shared=shared), tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
                config = dict(local=False, share=shared)
                with patch.object(assistant_local, 'read_config', return_value=config), patch.object(assistant_local, 'chat', return_value='Wrapped') as chat:
                    result = api.assistant_chat('Wrapped', [], project['path'], 'request', 'wrapped')
                self.assertTrue(result['ok'])
                chat.assert_called_once()
                if shared:
                    self.assertEqual(result['wrapped']['projects'], 1)
                    self.assertEqual(chat.call_args.kwargs['task'], 'wrapped')
                    self.assertEqual(json.loads(chat.call_args.args[3])['summary']['projects'], 1)
                else:
                    self.assertNotIn('wrapped', result)
                    self.assertEqual(chat.call_args.args[2:], ([], ''))

    def test_wrapped_period_api_and_persistence(self):
        api = app.Api.__new__(app.Api)
        rows = [dict(path='a.flp', name='A', created='2024-01-01', native=[], vst=[]),
                dict(path='b.flp', name='B', created='2025-01-01', native=[], vst=[])]
        api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=rows), meta={}, plays={})
        period = dict(start='2024-01-01', end='2024-12-31', field='created')
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            with patch.object(assistant_local, 'read_config', return_value=dict(local=True)), patch.object(assistant_local, 'chat', return_value='Wrapped') as chat:
                result = api.assistant_chat('Annual', task='wrapped', period=period)
                self.assertTrue(result['ok'])
                self.assertEqual(result['wrapped']['projects'], 1)
                self.assertEqual(json.loads(chat.call_args.args[3])['summary']['period'], period)
                invalid = api.assistant_chat('Annual', task='wrapped', period=dict(period, end='bad'))
                self.assertFalse(invalid['ok'])
                chat.assert_called_once()
            saved = api.assistant_chat_save('', [dict(role='user', content='Annual', mode='wrapped', wrapped_period=period, wrapped_kind='projects')])
            self.assertTrue(saved['ok'])
            self.assertEqual(api.assistant_chats()[0]['messages'][0]['wrapped_period'], period)
            self.assertEqual(api.assistant_chats()[0]['messages'][0]['wrapped_kind'], 'projects')


class CancellationTests(unittest.TestCase):
    def test_cancellable_transport_accepts_completed_json_and_sse(self):
        for streaming in (False, True):
            with self.subTest(streaming=streaming):
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        self.rfile.read(int(self.headers['Content-Length']))
                        body = b'data: {"choices":[{"delta":{"content":"Ciao"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n' if streaming else b'{"choices":[{"message":{"content":"Ciao"},"finish_reason":"stop"}]}'
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream' if streaming else 'application/json')
                        self.send_header('Content-Length', str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)

                server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.05), daemon=True)
                worker.start()
                generation = assistant_local.Generation()
                try:
                    with tempfile.TemporaryDirectory() as folder, patch.object(assistant_local, 'read_config', return_value=dict(url='http://127.0.0.1:' + str(server.server_port), model='test', local=True, share=True)):
                        answer = assistant_local.chat(folder, 'hello', [], '', progress=lambda *_: None, generation=generation)
                    self.assertEqual(answer, 'Ciao')
                finally:
                    generation.cancel()
                    server.shutdown()
                    server.server_close()
                    worker.join(2)

    def test_stop_disconnects_planning_answer_and_pending_headers(self):
        for phase in ('planning', 'answer', 'headers'):
            with self.subTest(phase=phase):
                ready, release = threading.Event(), threading.Event()
                calls = []

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *args):
                        pass

                    def do_POST(self):
                        calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                        if phase == 'headers':
                            ready.set()
                            release.wait(3)
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream')
                        self.end_headers()
                        delta = dict(reasoning_content='private planning') if phase == 'planning' else dict(content='Partial answer')
                        self.wfile.write(('data: ' + json.dumps(dict(choices=[dict(delta=delta)])) + '\n\n').encode())
                        self.wfile.flush()
                        ready.set()
                        release.wait(3)

                server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                server_thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.05), daemon=True)
                server_thread.start()
                api = app.Api.__new__(app.Api)
                api._store = SimpleNamespace(lock=threading.RLock(), state=dict(projects=[]), meta={}, plays={})
                result = []
                with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder), patch.object(assistant_local, 'read_config', return_value=dict(url='http://127.0.0.1:' + str(server.server_port), model='test', local=True, share=True)):
                    worker = threading.Thread(target=lambda: result.append(api.assistant_chat('hello', [], '', 'cancel-test', 'search' if phase == 'planning' else '')), daemon=True)
                    try:
                        worker.start()
                        self.assertTrue(ready.wait(2), repr(result))
                        if phase != 'headers':
                            deadline = time.monotonic() + 2
                            while time.monotonic() < deadline:
                                state = api.assistant_status('cancel-test')
                                if state.get('text') == 'Partial answer' or state.get('stage') == 'reasoning':
                                    break
                                threading.Event().wait(.01)
                            else:
                                self.fail('Streaming progress was not received')
                        self.assertFalse(api.assistant_stop('wrong-id')['ok'])
                        self.assertTrue(api.assistant_stop('cancel-test')['ok'])
                        worker.join(2)
                        self.assertFalse(worker.is_alive(), 'Cancellation must interrupt the blocked network read')
                        self.assertTrue(result[0]['cancelled'])
                        self.assertEqual(result[0]['answer'], 'Partial answer' if phase == 'answer' else '')
                        self.assertEqual(len(calls), 1)
                        self.assertTrue(calls[0]['stream'])
                        self.assertEqual(api._assistant_requests, {})
                        self.assertFalse(api.assistant_stop('cancel-test')['ok'])
                    finally:
                        release.set()
                        worker.join(3)
                        server.shutdown()
                        server.server_close()
                        server_thread.join(2)

    def test_cancelled_chat_preserves_partial_text(self):
        api = app.Api.__new__(app.Api)
        api._store = SimpleNamespace(lock=threading.RLock())
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'data_dir', return_value=folder):
            result = api.assistant_chat_save('', [dict(role='user', content='hello'), dict(role='assistant', content='partial', cancelled=True)])
            self.assertTrue(result['ok'])
            self.assertEqual(api.assistant_chats()[0]['messages'][1], dict(role='assistant', content='partial', cancelled=True))


if __name__ == '__main__':
    unittest.main()
