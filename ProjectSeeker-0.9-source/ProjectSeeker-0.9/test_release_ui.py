# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import argparse
import base64
import io
import json
from pathlib import Path
import tempfile
import time
import wave

import webview

from app import VERSION, fake_library


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', choices=['welcome', 'projects', 'map', 'album'])
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    ui = root / 'ui'
    projects = fake_library(60)
    for project, name in zip(projects, ['Neon Afterglow', 'Blue Hour', 'Velvet Rain', 'Night Drive', 'Paper Satellites', 'Morning Tape']):
        project['name'] = name
    projects[0]['hours'] = None
    projects[1]['hours'] = 0
    album = dict(id='night-signals', name='Night Signals', tracks=[p['path'] for p in projects[:6]], description='Ideas for the next EP')
    data = dict(projects=projects, paths=sorted({p['root'] for p in projects}), scanned={}, containers=[], pins=[],
                home='C:\\Demo', drives=['C:'], meta={}, plays={}, albums=dict(albums=[album], playlists=[], dur={}),
                kitpaths=[], kitlib={}, prefs=dict(lang='it', theme='dark', start='projects', tourDone=True), version=VERSION)
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(b'\0\0' * 22050 * 4)
    audio_url = 'data:audio/wav;base64,' + base64.b64encode(audio.getvalue()).decode('ascii')
    mock = '<script>window.__testErrors=[];window.__paths=' + json.dumps(data['paths']) + ';window.__MOCK__={get_state:async()=>(' + json.dumps(data) + '),set_prefs:async()=>({ok:true}),audio_url:async()=>({ok:true,url:' + json.dumps(audio_url) + '}),log_js:m=>window.__testErrors.push(m)};window.addEventListener("unhandledrejection",e=>window.__testErrors.push(String(e.reason)));</script>'
    html = (ui / 'index.html').read_text(encoding='utf-8').replace('<head>', '<head>' + mock, 1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', prefix='.test-release-', dir=ui, encoding='utf-8', delete=False) as stream:
        stream.write(html)
        preview = Path(stream.name)
    window = webview.create_window('Project Seeker - release preview (synthetic)', str(preview), width=1360, height=900)
    result = dict(ok=False, checks=0, screenshots=[])

    def capture(name):
        from System import Action
        from System.IO import MemoryStream
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        stream = MemoryStream()
        pending = {}
        window.native.webview.Invoke(Action(lambda: pending.update(task=window.native.webview.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream))))
        if not pending['task'].Wait(10000):
            raise TimeoutError('Screenshot capture timed out')
        output = root / 'docs' / 'screenshots' / (name + '.png')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(bytes(stream.ToArray()))
        stream.Dispose()
        result['screenshots'].append(output.relative_to(root).as_posix())

    def show(page, theme='dark'):
        window.evaluate_js('''(() => {
          const config=''' + json.dumps(dict(page=page, theme=theme)) + ''';
          S.prefs.fs=1;S.prefs.lang='en';S.prefs.theme=config.theme;pickLang();applyTheme();
          S.data.paths=config.page==='welcome'?[]:window.__paths;S.map=null;S.D=derive(S.data);
          S.sel=null;S.query='';S.flt={};S.ptab='all';S.coll=null;go(config.page==='map'?'home':'projects');
          if(config.page==='album')openColl('albums:night-signals');
        })()''')
        time.sleep(.2)

    def checks():
        try:
            for _ in range(100):
                if window.evaluate_js('!!S.D && !!document.querySelector("#q")'):
                    break
                time.sleep(.1)
            else:
                raise AssertionError(window.evaluate_js('({errors:window.__testErrors,state:!!S.data,mock:!!window.__MOCK__,url:location.href})'))
            for width in (1600, 1280, 900, 640):
                window.resize(width, 900)
                for language in ('it', 'en', 'fr', 'de'):
                    for theme in ('light', 'dark', 'black'):
                        config = json.dumps(dict(language=language, theme=theme))
                        count = window.evaluate_js('''(() => {
                          const c=''' + config + ''';
                          const check=(ok,label)=>{if(!ok)throw Error(label+' '+JSON.stringify(c)+' '+innerWidth);};
                          S.prefs.lang=c.language;S.prefs.theme=c.theme;S.prefs.fs=2;pickLang();applyTheme();
                          S.data.paths=[];go('home');
                          const main=document.querySelector('#main'),welcome=main.querySelector('.welcome');
                          check(!!welcome&&welcome.querySelectorAll('li').length===3,'welcome steps');
                          check(main.scrollWidth<=main.clientWidth+1,'welcome overflow');
                          check(welcome.querySelector('[data-act="add"]').textContent===T('Scegli cartella'),'folder action');
                          check(!rvOn()&&!document.querySelector('#nav [data-tab="reviver"]'),'beta off by default');
                          S.data.paths=window.__paths;S.map=null;S.D=derive(S.data);go('projects');S.ptab='all';S.sel=0;render();
                          check(document.querySelector('#detail').textContent.includes(T('– indica un dato non disponibile, non zero. Le ore sono quelle salvate da FL Studio; Ableton Live non le fornisce.')),'unknown data help');
                          check(fmtTime(S.D.P[0].hours)==='–'&&fmtTime(S.D.P[1].hours)!=='–','unknown versus zero');
                          S.sel=null;S.query='zzzznoresults';render();
                          check(!!document.querySelector('.project-empty [data-act="clearProjectFilters"]'),'search recovery');
                          document.querySelector('[data-act="clearProjectFilters"]').click();
                          check(filtered().length>0&&!S.query,'search reset');
                          S.settingsCategory='general';go('settings');tourStart();
                          return 8;
                        })()''')
                        result['checks'] += count
                        for step in range(4):
                            time.sleep(.03)
                            window.evaluate_js('''(() => {
                              const card=document.querySelector('#tour-card'),rect=card.getBoundingClientRect();
                              if(!document.querySelector('#app').inert||rect.left<0||rect.right>innerWidth+1||rect.top<0||rect.bottom>innerHeight+1)throw Error('tour bounds');
                              if(document.activeElement!==card.querySelector('[data-tour-next]'))throw Error('tour focus');
                              document.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
                              if(document.activeElement!==card.querySelector('[data-tour-skip]'))throw Error('tour focus trap');
                              tourNext();
                            })()''')
                            result['checks'] += 3
                        window.evaluate_js('''(() => {
                          if(S.tourOpen||document.querySelector('#app').inert||!document.activeElement.matches('[data-tour-start]'))throw Error('tour close focus');
                        })()''')
                        result['checks'] += 1
            window.evaluate_js('''(() => {
              const original=matchMedia;
              window.matchMedia=q=>q.includes('prefers-reduced-motion')?{matches:true}:original(q);
              S.sel=0;S.tab='projects';render();dfold('miss');
              if(!S.dOpen.miss||dsliding)throw Error('reduced motion detail');
              MP.viz='eq';if(vizOf()!=='line')throw Error('reduced motion player');
              S.sel=null;go('home');if(S.map.anim)throw Error('reduced motion map');
              window.matchMedia=original;MP.viz='line';
            })()''')
            result['checks'] += 3
            show('projects')
            window.evaluate_js("player.muted=true;loadTrack(mainAudio(S.D.P[0]).path,0,{play:false});")
            for _ in range(50):
                if window.evaluate_js('player.readyState>=2&&player.duration===4'):
                    break
                time.sleep(.05)
            else:
                raise AssertionError('synthetic WAV did not load')
            window.evaluate_js('player.play();')
            time.sleep(.2)
            window.evaluate_js('''(() => {
              if(player.paused||player.currentTime<=0)throw Error('synthetic playback');
              player.pause();player.currentTime=2;
              const track=S.track;go('folders');
              if(S.track!==track||!MP.shown)throw Error('player lost on navigation');
            })()''')
            result['checks'] += 3
            errors = window.evaluate_js('window.__testErrors')
            if errors:
                raise AssertionError(errors)
            if args.screenshots:
                window.resize(1360, 900)
                for page, theme in [('welcome', 'dark'), ('projects', 'dark'), ('projects', 'light'), ('projects', 'black'), ('map', 'dark'), ('album', 'dark')]:
                    show(page, theme)
                    capture(page + '-' + theme)
                show('projects')
                window.evaluate_js("S.sel=0;render();document.querySelector('#detail').scrollTop=360;")
                capture('details-player-dark')
            window.evaluate_js('mpClose();')
            if args.preview:
                window.resize(1360, 900)
                show(args.preview)
                window.evaluate_js("S.prefs.lang='it';pickLang();render();")
            result['ok'] = True
        except Exception as error:
            result['error'] = str(error)
        finally:
            print(json.dumps(result, ensure_ascii=True), flush=True)
            if not args.preview or not result['ok']:
                window.destroy()

    window.events.loaded += checks
    try:
        webview.start()
    finally:
        preview.unlink(missing_ok=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
