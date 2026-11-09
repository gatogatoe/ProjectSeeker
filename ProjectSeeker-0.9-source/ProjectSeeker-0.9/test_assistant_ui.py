# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import json
import sys
import tempfile
import time
from pathlib import Path

import webview
from app import fake_library


def main():
    ui = Path(__file__).resolve().parent / 'ui'
    projects = fake_library(30)
    data = dict(projects=projects, paths=[projects[0]['root']], scanned={}, containers=[], pins=[],
                home='C:\\Users\\Test', drives=['C:'], meta={}, kitpaths=[], prefs=dict(lang='it', start='assistant', tourDone=True))
    mock = '''<script>window.__testErrors=[];window.__calls=[];window.__MOCK__={
      get_state:async()=>window.__MOCK_DATA,set_prefs:async()=>({ok:true}),log_js:m=>window.__testErrors.push(m),
      assistant_config:async()=>({url:'http://localhost:1234/v1',model:'test',local:true}),assistant_chats:async()=>[],
      assistant_chat_save:async(id,messages)=>({ok:true,chat:{id:id||'a'.repeat(32),title:'Test',updated:'2026-11-07',messages}}),
      assistant_chat:async(...args)=>{window.__calls.push(args);return {ok:true,answer:'Found',projects:[{path:DATA.projects[0].path,name:DATA.projects[0].name}]};},
      open_project:async(path)=>{window.__calls.push(['open',path]);return {ok:true};}
    };</script>'''.replace('DATA.projects', 'window.__MOCK_DATA.projects')
    mock = mock.replace('<script>', '<script>window.__MOCK_DATA=' + json.dumps(data) + ';', 1)
    html = (ui / 'index.html').read_text(encoding='utf-8').replace('<head>', '<head>' + mock, 1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', prefix='.test-assistant-', dir=ui, encoding='utf-8', delete=False) as f:
        f.write(html)
        preview = Path(f.name)
    window = webview.create_window('Project Seeker - assistant test', str(preview), width=1280, height=900)
    result = dict(ok=False)

    def checks():
        try:
            for _ in range(100):
                if window.evaluate_js('!!document.querySelector("[data-as-suggest]")'):
                    break
                time.sleep(.1)
            if not window.evaluate_js('!!document.querySelector("[data-as-suggest]")'):
                raise RuntimeError(window.evaluate_js('({url:location.href,title:document.title,text:document.body.innerText.slice(0,500),errors:window.__testErrors})'))
            report = window.evaluate_js(r'''(() => {
              let n=0;const check=(v,m)=>{if(!v)throw Error(m);n++};
              check(document.querySelectorAll('[data-as-suggest]').length===3,'three start actions');
              document.querySelector('[data-as-suggest="0"]').click();
              check(document.querySelector('#as-text').value==='Cerca progetti: ','search starter');
              go('projects');S.sel=0;render();
              check(!!document.querySelector('[data-as-ask]'),'ask from detail');
              document.querySelector('[data-as-ask]').click();
              check(S.tab==='assistant'&&ASSIST.project===S.D.P[0].path,'selected project context');
              check(!!document.querySelector('.as-context'),'visible context');
              ASSIST.history=[{role:'assistant',content:'<img src=x onerror=alert(1)>',projects:[{path:S.D.P[0].path,name:'test'}]}];render();
              check(document.querySelectorAll('.as-card').length===1,'project card');
              check(!document.querySelector('.assistant-bubble img'),'response escaped');
              check(!!document.querySelector('.as-card [data-as-project]'),'project open action');
              check(!!document.querySelector('.as-card [data-showfile]'),'folder action');
              document.querySelector('[data-as-project]').click();
              check(window.__calls.at(-1)[0]==='open','reuse open project');
              assistantRestore({id:'b'.repeat(32),messages:[{role:'user',content:'hello',project_context:S.D.P[0].path}]});
              check(ASSIST.project===S.D.P[0].path,'restore project with chat');
              ASSIST.busy=true;render();
              check(document.querySelector('#as-text').disabled,'composer disabled while loading');
              check(document.querySelector('[data-as-reset]').disabled,'chat switching disabled');
              check(document.querySelector('.assistant-thread').getAttribute('aria-busy')==='true','accessible loading');
              ASSIST.busy=false;ASSIST.config.local=false;ASSIST.config.share=false;render();
              check(document.querySelector('.as-privacy').textContent.includes('solo il messaggio corrente'),'privacy notice');
              document.querySelector('[data-as-detach]').click();
              check(!ASSIST.project&&!document.querySelector('.as-context'),'remove context');
              check(!window.__testErrors.length,'no JS errors');
              return {checks:n};
            })()''')
            for width in (1280, 760, 540):
                window.resize(width, 900)
                for lang in ('it', 'en', 'fr', 'de'):
                    for theme in ('dark', 'light'):
                        layout = window.evaluate_js('''(() => {
                          LANG=LANG_VALUE;S.prefs.theme=THEME_VALUE;applyTheme();
                          ASSIST.history=[{role:'assistant',content:'Results',projects:[{path:S.D.P[0].path,name:'test'}]}];render();
                          const panel=document.querySelector('.assistant-layout'),card=document.querySelector('.as-card');
                          return {ok:panel.scrollWidth<=panel.clientWidth+1&&card.scrollWidth<=card.clientWidth+1,errors:window.__testErrors};
                        })()'''.replace('LANG_VALUE', json.dumps(lang)).replace('THEME_VALUE', json.dumps(theme)))
                        if not layout['ok'] or layout['errors']:
                            raise AssertionError(('layout', width, lang, theme, layout))
                        report['checks'] += 1
            window.evaluate_js("LANG='it';S.prefs.theme='dark';ASSIST.history=[];ASSIST.project=S.D.P[0].path;render();document.querySelector('#as-text').value='Titoli?';assistantSend();")
            for _ in range(100):
                if window.evaluate_js('!ASSIST.busy'):
                    break
                time.sleep(.1)
            sent = window.evaluate_js("({ok:ASSIST.history.length===2&&ASSIST.history[1].content==='Found'&&window.__calls.at(-1)[2]===S.D.P[0].path&&!!document.querySelector('.as-card'),errors:window.__testErrors})")
            if not sent['ok'] or sent['errors']:
                raise AssertionError(('send', sent))
            report['checks'] += 1
            result.update(ok=True, **report)
        except Exception as exc:
            result['error'] = str(exc)
        finally:
            print(json.dumps(result), flush=True)
            window.destroy()

    window.events.loaded += checks
    try:
        webview.start()
    finally:
        preview.unlink(missing_ok=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
