# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import glob
import hashlib
import logging
import os
import re
import subprocess
import threading
import xml.etree.ElementTree as ET

REVIVER_HELP = 'Su macOS aggiungi manualmente la cartella Reviver nelle impostazioni File di FL Studio, poi aggiorna il progetto.'
KEYCHAIN_ERROR = 'Impossibile accedere al Portachiavi di macOS'
log = logging.getLogger('ProjectSeeker')


def sys_lang():
    result = subprocess.run(['defaults', 'read', '-g', 'AppleLanguages'], capture_output=True, text=True, timeout=5)
    match = re.search(r'[a-z]{2}', result.stdout.lower())
    return match.group() if match and match.group() in ('it', 'fr', 'de') else 'en'


def fl_apps():
    found = glob.glob('/Applications/FL Studio*.app') + glob.glob(os.path.expanduser('~/Applications/FL Studio*.app'))
    return sorted(found, key=os.path.getmtime, reverse=True)


def fl_installs():
    return [os.path.join(path, 'Contents', 'Resources', 'FL') for path in fl_apps()]


def drives():
    try:
        return [name for name in os.listdir('/Volumes') if not name.startswith('.')]
    except OSError:
        return []


def search_dirs():
    path = os.path.expanduser('~/Library/Preferences/Image-Line/reg.xml')
    if not os.path.isfile(path):
        return []
    try:
        root = ET.parse(path).getroot()
        versions = {}

        def walk(element, version=None, inside=False):
            name = element.get('name') or element.get('Name') or element.get('key') or element.tag
            match = re.fullmatch(r'FL Studio (\d+)', name.strip())
            version = int(match.group(1)) if match else version
            inside = inside or name.strip().lower() == 'search paths'
            if inside and version is not None:
                for value in [element.text] + [element.get(key) for key in ('value', 'Value', 'data')]:
                    if value and value.strip():
                        versions.setdefault(version, []).append(value.strip())
            for child in element:
                walk(child, version, inside)

        walk(root)
        for version in sorted(versions, reverse=True):
            found = []
            for value in versions[version]:
                value = value[1:].split('"', 1)[0] if value.startswith('"') else value.split(',', 1)[0]
                value = os.path.normpath(os.path.expanduser(os.path.expandvars(value.strip())))
                if value not in found and os.path.isdir(value):
                    found.append(value)
            if found:
                return found
    except (OSError, ET.ParseError, ValueError) as error:
        log.info('FL search paths not read: %s', error)
    return []


def fl_running():
    result = subprocess.run(['pgrep', '-if', r'/FL Studio[^/]*\.app/Contents/MacOS/'], capture_output=True, timeout=10)
    return result.returncode == 0


def open_path(path):
    if subprocess.run(['open', path], capture_output=True, timeout=20).returncode:
        raise OSError('open failed: ' + path)


def reveal(path):
    subprocess.Popen(['open', '-R', path])


def on_main(action):
    from Foundation import NSThread
    from PyObjCTools import AppHelper
    if NSThread.isMainThread():
        return action()
    done = threading.Event()
    results = []

    def call():
        try:
            results.append((True, action()))
        except Exception as error:
            results.append((False, error))
        finally:
            done.set()

    AppHelper.callAfter(call)
    if not done.wait(10):
        raise OSError('macOS window did not respond')
    ok, result = results[0]
    if not ok:
        raise result
    return result


_drag_source_type = None


def start_drag(window, path):
    global _drag_source_type
    import AppKit
    import objc
    from Foundation import NSObject, NSURL

    if _drag_source_type is None:
        class ProjectSeekerDragSource(NSObject, protocols=[objc.protocolNamed('NSDraggingSource')]):
            def draggingSession_sourceOperationMaskForDraggingContext_(self, session, context):
                return AppKit.NSDragOperationCopy

            def ignoreModifierKeysForDraggingSession_(self, session):
                return True

        _drag_source_type = ProjectSeekerDragSource

    def begin():
        event = AppKit.NSApp.currentEvent()
        if event is None:
            return dict(ok=False, error='Operazione non riuscita')
        view = window.native.contentView()
        point = view.convertPoint_fromView_(event.locationInWindow(), None)
        item = AppKit.NSDraggingItem.alloc().initWithPasteboardWriter_(NSURL.fileURLWithPath_(path))
        icon = AppKit.NSWorkspace.sharedWorkspace().iconForFile_(path)
        icon.setSize_((32, 32))
        item.setDraggingFrame_contents_(((point.x, point.y), (32, 32)), icon)
        source = _drag_source_type.alloc().init()
        window._mac_drag_source = source
        view.beginDraggingSessionWithItems_event_source_([item], event, source)
        return dict(ok=True)

    return on_main(begin)


def _account(folder):
    return hashlib.sha256(os.path.realpath(folder).encode('utf-8')).hexdigest()


def has_key(folder):
    return os.path.isfile(os.path.join(folder, 'assistant.keychain'))


def read_key(folder):
    if not has_key(folder):
        return ''
    try:
        from keyring.backends.macOS import Keyring
        key = Keyring().get_password('ProjectSeeker API', _account(folder))
        if key is None:
            raise OSError(KEYCHAIN_ERROR)
        return key
    except Exception as error:
        raise OSError(KEYCHAIN_ERROR) from error


def save_key(folder, key):
    marker = os.path.join(folder, 'assistant.keychain')
    try:
        from keyring.backends.macOS import Keyring
        backend = Keyring()
        account = _account(folder)
        if key:
            backend.set_password('ProjectSeeker API', account, key)
            temporary = marker + '.tmp'
            with open(temporary, 'w', encoding='utf-8') as stream:
                stream.write('macOS Keychain\n')
            os.replace(temporary, marker)
        elif has_key(folder):
            if backend.get_password('ProjectSeeker API', account) is not None:
                backend.delete_password('ProjectSeeker API', account)
            os.remove(marker)
    except Exception as error:
        raise OSError(KEYCHAIN_ERROR) from error


def build_check(app, output):
    import json
    from pathlib import Path
    import platform
    import tempfile
    import time
    import traceback
    import wave
    import webview

    output = Path(output).resolve()
    result = dict(ok=False, arch=platform.machine(), frozen=bool(getattr(app.sys, 'frozen', False)), checks=0)
    with tempfile.TemporaryDirectory(prefix='projectseeker-build-check-') as folder:
        previous = app.data_dir
        app.data_dir = lambda: folder
        api = app.Api()
        projects = app.fake_library(12)
        for i, project in enumerate(projects):
            project.update(path=os.path.join(folder, 'Project %d.flp' % i), dir=folder, root=folder, samples=[], exports=[])
        audio = os.path.join(folder, 'preview.wav')
        with wave.open(audio, 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(22050)
            stream.writeframes(b'\0\0' * 22050 * 4)
        projects[0]['exports'] = [('preview.wav', os.path.getsize(audio), 100)]
        api._store.state.update(projects=projects, paths=[folder], prefs=dict(lang='en', theme='dark', start='projects', tourDone=True, autoscan=False))
        base = getattr(app.sys, '_MEIPASS', str(Path(app.__file__).parent))
        window = webview.create_window('Project Seeker - build check', os.path.join(base, 'ui', 'index.html'), js_api=api, width=1360, height=900)
        api._window = window
        window.events.before_show += api._install_window_frame
        window.events.loaded += api._watch_drops

        def checks():
            try:
                for attempt in range(150):
                    if window.evaluate_js('typeof S !== "undefined" && !!S.D && S.D.P.length === 12'):
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError('Packaged UI did not initialize')
                window.evaluate_js('window.__buildErrors=[];window.addEventListener("error",e=>window.__buildErrors.push(e.message));window.addEventListener("unhandledrejection",e=>window.__buildErrors.push(String(e.reason)));')
                for language in ('it', 'en', 'fr', 'de'):
                    for theme in ('light', 'dark', 'black'):
                        config = json.dumps(dict(language=language, theme=theme))
                        count = window.evaluate_js('''(() => {
                          const c=''' + config + ''';
                          const check=(ok,label)=>{if(!ok)throw Error(label+' '+JSON.stringify(c));};
                          S.prefs.lang=c.language;S.prefs.theme=c.theme;pickLang();applyTheme();
                          check(IS_MAC && SEP==='/', 'macOS platform');
                          check(document.documentElement.lang===c.language,'language');
                          check(document.querySelector('.window-controls').hidden,'native window controls');
                          let n=3;
                          for(const page of ['home','projects','folders','assistant','settings','scan']) {
                            go(page);check(document.querySelector('#main').textContent.trim().length>0,page);n++;
                          }
                          for(const [id] of SETTINGS_CATEGORIES) {selectSettingsCategory(id);}
                          check(T('Come macOS').includes('macOS'),'macOS labels');n++;
                          check(mainAudio(S.D.P[0]).path.endsWith('/preview.wav'),'audio path');n++;
                          go('projects');return n;
                        })()''')
                        result['checks'] += count
                response = api.audio_url(audio)
                if not response['ok']:
                    raise AssertionError(response)
                window.evaluate_js('player.src=' + json.dumps(response['url']) + ';player.load();')
                for attempt in range(100):
                    if window.evaluate_js('Number.isFinite(player.duration) && Math.abs(player.duration-4)<.1'):
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError('WKWebView could not load WAV metadata')
                result['checks'] += 1
                go_result = window.evaluate_js('go("settings");Math.abs(player.duration-4)<.1')
                if not go_result:
                    raise AssertionError('Audio state lost on navigation')
                result['checks'] += 1
                errors = window.evaluate_js('window.__buildErrors')
                if errors:
                    raise AssertionError(errors)
                result.update(ok=True, webview='WKWebView', audio='4 second synthetic WAV loaded', languages=['it', 'en', 'fr', 'de'])
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                window.destroy()

        try:
            webview.start(checks)
        finally:
            app.data_dir = previous
    if not result['ok']:
        raise RuntimeError(result)
