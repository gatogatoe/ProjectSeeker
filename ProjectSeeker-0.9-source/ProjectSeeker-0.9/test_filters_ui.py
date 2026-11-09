# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""UI integration checks with an invented library; never loads user data.

Run with Python and pywebview installed. Add --preview to inspect the window
after the checks; closing it also removes the temporary preview HTML.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

import webview
from app import fake_library


def main():
    ui = Path(__file__).resolve().parent / 'ui'
    projects = fake_library(300)
    data = dict(projects=projects, paths=[projects[0]['root']], scanned={},
                containers=[], pins=[], home='C:\\Users\\Test', drives=['C:'],
                meta={}, kitpaths=[], prefs=dict(lang='it', ptab='all', start='projects', tourDone=True))
    data['meta'][projects[0]['path'].lower()] = dict(tags=['Trap', '<Kit & "test">'], star=True)
    mock = '<script>window.__testErrors=[];window.__MOCK__={get_state:async()=>(' + json.dumps(data) + '),set_prefs:async()=>({ok:true}),log_js:m=>window.__testErrors.push(m)};</script>'
    html = (ui / 'index.html').read_text(encoding='utf-8').replace('<head>', '<head>' + mock, 1)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', prefix='.test-filters-', dir=ui, encoding='utf-8', delete=False) as f:
        f.write(html)
        preview = Path(f.name)
    window = webview.create_window('Project Seeker - filter design test', str(preview), width=1280, height=900)
    result = dict(ok=False)

    def checks():
        try:
            for _ in range(100):
                if window.evaluate_js('!!document.querySelector("#project-filter-toggle")'):
                    break
                time.sleep(.1)
            report = window.evaluate_js(r'''(() => {
              let n=0; const check=(v,m)=>{if(!v)throw Error(m);n++};
              const $el=s=>document.querySelector(s);
              const click=s=>$el(s).click();
              const change=(s,v)=>{const el=$el(s);el.value=v;el.dispatchEvent(new Event('change',{bubbles:true}));};
              const reset=()=>click('[data-act="clearProjectFilters"]');
              const members=p=>[p,...(p.copies||[]).map(id=>S.D.P[id])];
              check(S.D.P.length===300,'invented library');
              const initial=filtered().length;
              click('[data-ptab="foryou"]');
              check(!!$el('#q')&&!!$el('.fy'),'For you search and shelves');
              const fyQuery=$el('#q');fyQuery.focus();fyQuery.value='zzzzzzzzzznoresults';fyQuery.dispatchEvent(new Event('input',{bubbles:true}));
              check(!!$el('.project-empty')&&!$el('.fy'),'For you search results');
              check($el('#q')===fyQuery&&document.activeElement===fyQuery,'search keeps input focus');
              reset();check(!!$el('.fy')&&!$el('#rows'),'For you reset restores shelves');
              change('[data-pfilter="plugins"]','Serum');
              check(!!$el('#rows')&&filtered().length>0,'For you plugin filter');
              reset();click('[data-ptab="all"]');
              check($el('#project-filter-panel').hidden,'panel starts closed');
              check($el('#q').placeholder==='Cerca nome, cartella o plugin…','simple placeholder');
              check($el('#quick').children.length===2,'two visible shortcuts');
              check(!$el('[data-pdirection]'),'single sort menu');
              click('#project-filter-toggle');
              check(!$el('#project-filter-panel').hidden,'open panel');
              check($el('#project-filter-toggle').getAttribute('aria-expanded')==='true','expanded accessibility');
              check($el('[data-psection="music"]').open,'music expanded');
              check(!$el('[data-psection="dates"]').open,'dates collapsed');
              check(!$el('[data-psection="files"]').open,'files collapsed');
              check($el('[data-pfilter="plugins"]').list.options.length>10,'searchable plugins');
              const year=S.D.P.find(p=>p.year!=='?').year;
              change('[data-pfilter="year"]',year);
              check(filtered().length>0&&filtered().every(p=>members(p).some(x=>x.year===year)),'year filter');
              check($el('#chips').textContent.includes(year),'active filter chip');
              check($el('.filter-count').textContent==='1','filter count');
              change('[data-prange="bpm"][data-bound="min"]','130');
              check(filtered().every(p=>members(p).some(x=>x.year===year&&x.bpm!=null&&Math.round(x.bpm)>=130)),'combined BPM');
              check($el('.filter-count').textContent==='2','combined count');
              click('[data-act="closeProjectFilters"]');
              check($el('#project-filter-panel').hidden,'close panel');
              check($el('#chips').textContent.includes(year),'chips visible when closed');
              check(document.activeElement.id==='project-filter-toggle','focus returns to toggle');
              click('[data-unchip="year"]');
              check(!S.F.year&&$el('[data-pfilter="year"]').value==='','chip clears menu');
              check($el('.filter-count').textContent==='1','chip updates count');
              reset();check(filtered().length===initial&&!$el('.filter-count'),'reset');
              click('[data-quick="missing"]');
              check(filtered().every(p=>members(p).some(x=>!x.error&&x.miss>0)),'quick missing');
              check($el('[data-pfilter="missing"]').value==='true','quick syncs menu');
              reset();
              click('#project-filter-toggle');
              change('[data-pfilter="plugins"]','Serum');
              check(filtered().length>0&&filtered().every(p=>members(p).some(x=>x.nPlug.some(n=>n.includes('serum')))),'plugin typed');
              reset();
              const q=$el('#q');q.value='anno:'+year+' beat';q.dispatchEvent(new Event('input',{bubbles:true}));
              change('[data-pfilter="year"]','2026');
              check(S.F.year.min===2026&&S.query==='beat','menu replaces typed criterion');
              reset();
              for(const [key] of PROJECT_SORTS)for(const reverse of [false,true]){
                change('[data-psort]',key+':'+(reverse?'reverse':'default'));
                const rows=filtered(),cmp=CMP[key];
                check(S.sort===key&&S.rev===reverse&&rows.every((p,i)=>!i||(reverse?cmp(rows[i-1],p)>=0:cmp(rows[i-1],p)<=0)),'sort '+key+' '+reverse);
              }
              click('[data-sortcol="name"]');
              check($el('[data-psort]').value==='name:default','column syncs menu');
              click('[data-sortcol="name"]');
              check($el('[data-psort]').value==='name:reverse','column syncs reverse');
              change('[data-pgroup]','same');
              check(S.filter==='same'&&$el('[data-pview="grid"]').disabled,'grouped view');
              change('[data-pfilter="year"]',year);reset();check($el('[data-pgroup]').value==='all','reset syncs grouping');
              click('[data-pview="grid"]');
              change('[data-psort]','mod:default');
              check(!!$el('#rows.cgrid')&&S.sort==='mod','grid sorting');
              applyFilter({text:'zzzzzzzzzznoresults'});
              check(!!$el('.project-empty')&&$el('.project-empty').textContent.includes('Nessun progetto'),'empty state');
              click('.project-empty [data-act="clearProjectFilters"]');
              check(filtered().length===initial&&S.query==='','empty state reset');
              S.F={plugins:['Plugin assente']};render();
              check($el('[data-pfilter="plugins"]').value==='Plugin assente','saved absent plugin');
              S.F={};S.query='';S.filter='all';S.sort='mod';S.rev=false;S.prefs.pview='list';S.projectFiltersOpen=false;
              for(const lang of ['en','fr','de','it']){
                LANG=lang;render();
                check(!!$el('#project-filter-toggle')&&!!$el('[data-psort]'),'render '+lang);
                if(lang!=='it')check($el('[data-psort]').selectedOptions[0].textContent!==PROJECT_SORTS[0][1],'translated sort '+lang);
              }
              const top=$el('#rows').getBoundingClientRect().top;
              click('#project-filter-toggle');
              check(getComputedStyle($el('#project-filter-panel')).position==='absolute'&&$el('#rows').getBoundingClientRect().top===top,'floating panel preserves result position');
              document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
              check($el('#project-filter-panel').hidden&&document.activeElement.id==='project-filter-toggle','Escape closes and restores focus');
              click('#project-filter-toggle');
              $el('#q').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));
              check($el('#project-filter-panel').hidden,'outside pointer closes');
              check(!window.__testErrors.length,'no JS errors: '+window.__testErrors.join(';'));
              return {checks:n,unique:initial};
            })()''')
            for width in (1280, 980):
                window.resize(width, 900)
                time.sleep(.25)
                for lang in ('it', 'en', 'fr', 'de'):
                    for theme in ('dark', 'light'):
                        layout = window.evaluate_js('''(() => {
                          LANG=''' + json.dumps(lang) + ''';S.prefs.theme=''' + json.dumps(theme) + ''';S.projectFiltersOpen=true;applyTheme();render();
                          const panel=document.querySelector('#project-filter-panel'),search=document.querySelector('.project-search');
                          const r=panel.getBoundingClientRect(),s=search.getBoundingClientRect();
                          return {ok:panel.scrollWidth<=panel.clientWidth+1&&r.left>=s.left-1&&r.right<=s.right+1,errors:window.__testErrors};
                        })()''')
                        if not layout['ok'] or layout['errors']:
                            raise AssertionError(('layout', width, lang, theme, layout))
                        report['checks'] += 1
            window.resize(1280, 900)
            window.evaluate_js("LANG='it';S.prefs.theme='dark';S.projectFiltersOpen=false;applyTheme();render();")
            result.update(ok=True, **report)
            print(json.dumps(result), flush=True)
        except Exception as exc:
            result['error'] = str(exc)
            result['js_errors'] = window.evaluate_js('window.__testErrors || []')
            print(json.dumps(result), flush=True)
        finally:
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
