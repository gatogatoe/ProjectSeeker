# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
import json
from pathlib import Path
import sys
import tempfile
import time

import webview

from app import fake_library


def main():
    ui = Path(__file__).resolve().parent / 'ui'
    projects = fake_library(60)
    projects[0].update(name='constructor', title='Città 日本語 🎵', gen=['VST non identificato'], fx=[])
    data = dict(projects=projects, paths=[projects[0]['root']], scanned={}, containers=[], pins=[],
                home='C:\\Users\\Test', drives=['C:'], meta={}, plays={}, albums=dict(albums=[], playlists=[], dur={}),
                kitpaths=[], kitlib={}, prefs=dict(lang='it', start='projects', tourDone=True, reviver=True))
    data['kitpaths'] = ['C:\\Kits']
    data['kitlib'] = {'C:\\Kits': dict(parts=[dict(sub='Pack', files=[['kick.wav', 4]])], scanned='2026-11-08 12:00', inaccessible=['C:\\Kits\\Pack'])}
    mock = '<script>window.__testErrors=[];window.__MOCK__={get_state:async()=>(' + json.dumps(data) + '),set_prefs:async()=>({ok:true}),log_js:m=>window.__testErrors.push(m)};</script>'
    html = (ui / 'index.html').read_text(encoding='utf-8').replace('<head>', '<head>' + mock, 1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', prefix='.test-pages-', dir=ui, encoding='utf-8', delete=False) as stream:
        stream.write(html)
        preview = Path(stream.name)
    window = webview.create_window('Project Seeker - synthetic page checks', str(preview), width=1280, height=900)
    result = dict(ok=False)

    def checks():
        try:
            for _ in range(100):
                if window.evaluate_js('!!document.querySelector("#project-filter-toggle")'):
                    break
                time.sleep(.1)
            window.evaluate_js('''window.__missingTranslations=[];
              const originalT=T;
              T=function(s,v){if(LANG!=='it'&&typeof s==='string'&&!Object.hasOwn(DICT[LANG],s))window.__missingTranslations.push(s);return originalT(s,v);};
            ''')
            count = 0
            for width in (1600, 1280, 800, 640):
                window.resize(width, 900)
                for language in ('it', 'en', 'fr', 'de'):
                    for theme in ('black', 'dark', 'light'):
                        state = json.dumps(dict(language=language, theme=theme))
                        report = window.evaluate_js('''(() => {
                          const config=''' + state + ''';
                          S.prefs.lang=config.language;S.prefs.theme=config.theme;pickLang();applyTheme();S.D=derive(S.data);
                          let checks=0;
                          for(const tab of ['home','projects','folders','reviver','scan','settings','assistant']){
                            go(tab);
                            if(S.tab!==tab||!document.querySelector('#main').textContent.trim())throw Error('empty page '+tab);
                            if(tab==='scan'){
                              const retry=document.querySelector('[data-kitrescan]');
                              if(retry.textContent!==T('Riprova')||!retry.closest('.set-r').textContent.includes(T('Conservati i dati precedenti delle parti non accessibili.')))throw Error('missing kit scan warning');
                            }
                            if(tab==='settings'){
                              if(document.querySelectorAll('[data-settings-category]').length!==7)throw Error('missing settings categories');
                              const model=document.querySelector('#as-model');model.value='unsaved-model';
                              for(const category of SETTINGS_CATEGORIES){
                                document.querySelector('[data-settings-category="'+category[0]+'"]').click();
                                const panes=[...document.querySelectorAll('[data-settings-pane]')].filter(p=>!p.hidden);
                                if(panes.length!==1||panes[0].dataset.settingsPane!==category[0])throw Error('incorrect settings category');
                                if(document.querySelectorAll('[data-settings-category][aria-current]').length!==1)throw Error('incorrect selected category');
                                if(document.querySelector('#as-model')!==model||model.value!=='unsaved-model')throw Error('lost settings draft');
                                const main=document.querySelector('#main');
                                if(main.scrollWidth>main.clientWidth+1)throw Error('settings overflow: '+config.language+' '+category[0]+' '+innerWidth);
                                const box=main.getBoundingClientRect();
                                for(const control of panes[0].querySelectorAll('button,input,select')){
                                  const rect=control.getBoundingClientRect();
                                  if(rect.width&&(rect.left<box.left||rect.right>box.right+1))throw Error('settings control outside panel: '+category[0]);
                                }
                                checks++;
                              }
                              S.prefs.fs=2;applyTheme();render();
                              for(const category of SETTINGS_CATEGORIES){
                                selectSettingsCategory(category[0]);
                                const main=document.querySelector('#main');
                                if(main.scrollWidth>main.clientWidth+1)throw Error('large settings text overflow: '+category[0]);
                                checks++;
                              }
                              S.prefs.fs=1;applyTheme();render();
                              go('assistant');document.querySelector('[data-as-settings]').click();
                              if(S.tab!=='settings'||document.querySelector('#settings-pane-assistant').hidden||document.activeElement.id!=='as-provider')throw Error('assistant settings shortcut');
                              if(Math.abs(document.querySelector('#as-model').getBoundingClientRect().height-document.querySelector('#as-key').getBoundingClientRect().height)>1)throw Error('inconsistent assistant input heights');
                              go('home');go('settings');
                              if(document.querySelector('#settings-pane-assistant').hidden)throw Error('lost settings category after navigation');
                              checks+=2;
                            }
                            checks++;
                          }
                          go('projects');S.ptab='all';S.sel=0;render();
                          if(document.querySelector('#detail').hidden)throw Error('missing detail');
                          if(config.language!=='it'&&document.querySelector('#detail').textContent.includes('VST non identificato'))throw Error('untranslated generator');
                          S.error='File non trovato: C:\\\\file vuoto\\\\test.wav';render();
                          if(!document.querySelector('#errbar').textContent.includes('C:\\\\file vuoto\\\\test.wav'))throw Error('translated path');
                          S.error='';
                          return {checks:checks+2,errors:window.__testErrors};
                        })()''')
                        if report['errors']:
                            raise AssertionError(report['errors'])
                        count += report['checks']
            missing = window.evaluate_js('[...new Set(window.__missingTranslations)].sort()')
            allowed = {'Italiano', 'English', 'Français', 'Deutsch', 'Ollama', 'OpenAI', 'OpenRouter', 'Groq', 'Together AI', 'DeepSeek', 'Mistral AI', 'DAW', 'EQ', 'Reviver', 'File non trovato: C:\\file vuoto\\test.wav'}
            missing = [text for text in missing if text not in allowed]
            if missing:
                raise AssertionError(('untranslated dynamic keys', missing))
            result.update(ok=True, checks=count)
            if '--preview' in sys.argv:
                window.resize(1440, 960)
                window.evaluate_js("S.prefs.lang='it';S.prefs.theme='dark';pickLang();applyTheme();S.settingsCategory='appearance';go('settings');")
        except Exception as error:
            result['error'] = str(error)
            result['js_errors'] = window.evaluate_js('window.__testErrors || []')
        finally:
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if '--preview' not in sys.argv or not result['ok']:
                window.destroy()

    window.events.loaded += checks
    try:
        webview.start()
    finally:
        preview.unlink(missing_ok=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
