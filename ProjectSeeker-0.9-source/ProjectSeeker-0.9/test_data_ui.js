// Copyright (C) 2026 Gato
// SPDX-License-Identifier: GPL-3.0-only
// Licensed under the GNU General Public License v3.0; see LICENSE.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

const html = fs.readFileSync(path.join(__dirname, 'ui/index.html'), 'utf8');
const extract = (start, end) => {
  const at = html.indexOf(start);
  assert.ok(at >= 0, start);
  const to = html.indexOf(end, at);
  assert.ok(to > at, end);
  return html.slice(at, to);
};
const dictionaries = {};
for (const lang of ['en', 'fr', 'de']) {
  const context = {window: {}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'ui/lang', lang + '.js'), 'utf8'), context);
  dictionaries[lang] = context.window['LANG_' + lang.toUpperCase()];
}
function ui() {
  const context = vm.createContext({window: {}, console, navigator: {language: 'en'}, document: {}, S: {prefs: {}}});
  for (const lang of ['en', 'fr', 'de']) context.window['LANG_' + lang.toUpperCase()] = dictionaries[lang];
  vm.runInContext(extract('const esc =', 'const S =') + '\n' + extract('const LANGS =', '/* ---------------------------------------------------------------- bridge') + '\n' + extract('const GENERIC =', 'const whyOf =') + '\n' + extract('const ST_ORDER =', '// group of a project') + '\n' + extract('const COLS =', 'const applyFilter ='), context);
  return code => vm.runInContext(code, context);
}
const project = (name, extra = {}) => ({path: 'C:\\beats\\' + name + '.flp', dir: 'C:\\beats', root: 'C:\\beats', folder: 'beats', name, version: '', created: '', modified: '', hours: null, bpm: null, kb: 1, backups: 0, samples: [], native: [], vst: [], ...extra});
const data = projects => JSON.stringify({projects, home: 'C:\\Users\\Test'});

test('project and kit names that match object properties remain valid data', () => {
  for (const name of ['constructor', '__proto__', 'tostring', 'Città 日本語 🎵']) {
    const run = ui();
    run('S.D=derive(' + data([project(name, {samples: [{p: 'C:\\' + name + '\\kick.wav', e: false}]})]) + ')');
    assert.equal(run('S.D.P[0].name'), name);
    assert.equal(run('S.D.KITS.length'), 1);
    assert.equal(run('S.D.KITS[0].files.size'), 1);
  }
});
test('unknown hours do not match a numeric hours filter', () => {
  const run = ui();
  run('S.D=derive(' + data([project('unknown'), project('zero', {hours: 0}), project('two', {hours: 2})]) + ')');
  assert.equal(run('searchProjects({hours:{max:1}}).map(p=>p.name).join(",")'), 'zero');
  assert.equal(run('searchProjects({hours:{min:0}}).length'), 2);
});
test('library time totals distinguish unknown hours from an actual zero', () => {
  const run = ui();
  run(extract('function projHead()', 'function viewForYou()'));
  run(extract('function statsData()', 'function viewHome()'));
  run('S.D=derive(' + data([project('unknown', {created: '2026-01-01'}), project('live', {daw: 'Ableton Live', created: '2026-01-02'})]) + ')');
  assert.equal(run('S.D.tot.timed'), 0);
  assert.ok(run('projHead()').includes('<b>–</b>'));
  assert.equal(run('statsData().years.filter(([,v])=>v.known).length'), 0);
  run('S.D=derive(' + data([project('unknown'), project('zero', {hours: 0, created: '2026-01-01'})]) + ')');
  assert.equal(run('S.D.tot.timed'), 1);
  assert.ok(run('projHead()').includes('<b>0m</b>'));
  assert.equal(run('statsData().years.filter(([,v])=>v.known).length'), 1);
  run('S.D=derive(' + data([project('unknown'), project('two', {hours: 2})]) + ')');
  assert.equal(run('S.D.tot.h'), 2);
  assert.ok(run('projHead()').includes('<b>2h 00m</b>'));
  run('S.D=derive(' + data([project('unknown'), project('zero', {hours: 0}), project('two', {hours: 2})]) + ')');
  run("colChart=()=>'';barList=()=>'';calendar=()=>''");
  assert.ok(run('statsPage()').includes('Media per progetto</small><b>1h 00m</b>'));
});
test('translation fallback never invokes inherited object properties', () => {
  const run = ui();
  for (const lang of ['it', 'en', 'fr', 'de']) {
    run('LANG=' + JSON.stringify(lang));
    assert.equal(run('T("constructor")'), 'constructor');
    assert.equal(run('T("toString")'), 'toString');
    assert.equal(run('T("Unknown {n}", {n:2})'), 'Unknown 2');
  }
});
test('backend errors are translated without rewriting file paths', () => {
  const run = ui();
  run('LANG="en"');
  assert.equal(run('trErr("Conversazione non valida")'), 'Invalid conversation');
  assert.equal(run('trErr("Impossibile raggiungere il modello")'), 'Could not reach the model');
  assert.equal(run('trErr("File non trovato: C:\\\\file vuoto\\\\test.wav")'), 'File not found: C:\\file vuoto\\test.wav');
  assert.equal(run('trErr("Il provider ha risposto con HTTP 429")'), 'The provider returned HTTP 429');
  assert.equal(run('trErr("Il provider ha risposto con HTTP 400. Controlla se il modello supporta il livello di ragionamento scelto.")'), 'The provider returned HTTP 400. Check whether the model supports the selected reasoning level.');
  for (const lang of ['en', 'fr', 'de']) {
    run('LANG=' + JSON.stringify(lang));
    assert.equal(run('trErr("Impossibile raggiungere il modello")'), dictionaries[lang]['Impossibile raggiungere il modello']);
    assert.notEqual(run('trErr("Conversazione non valida")'), 'Conversazione non valida');
  }
});
test('size formatting follows the selected language', () => {
  const run = ui();
  for (const lang of ['it', 'fr', 'de']) {
    run('LANG=' + JSON.stringify(lang));
    assert.equal(run('fmtSize(1536)'), '1,5 MB');
  }
  run('LANG="en"');
  assert.equal(run('fmtSize(1536)'), '1.5 MB');
  for (const value of ['null', 'undefined', 'NaN']) assert.equal(run('fmtSize(' + value + ')'), '–');
});
test('dates and Italian singulars handle missing and boundary values', () => {
  const run = ui();
  run("const MESI=['gen','feb','mar','apr','mag','giu','lug','ago','set','ott','nov','dic']");
  for (const lang of ['it', 'en', 'fr', 'de']) {
    run('LANG=' + JSON.stringify(lang));
    for (const value of ['null', 'undefined', '42', '"bad"', '"2023-02-29"']) assert.equal(run('fmtDate(' + value + ')'), '–');
    assert.notEqual(run('fmtDate("2024-02-29")'), '–');
    for (let month = 1; month <= 12; month++) assert.ok(!run('fmtDate(' + JSON.stringify('2024-' + String(month).padStart(2, '0') + '-01') + ')').includes('undefined'));
  }
  run('LANG="it"');
  assert.equal(run('T("{n} progetti trovati",{n:1})'), '1 progetto trovato');
});
test('preference saves retain call order and report failures', async () => {
  const calls = [], errors = [];
  let release;
  const context = vm.createContext({S: {prefs: {theme: 'dark'}, hide: {}}, api: () => ({set_prefs: prefs => {
    calls.push(prefs);
    if (calls.length === 1) return new Promise(resolve => {release = resolve;});
    return Promise.resolve({ok: false, error: 'disk full'});
  }}), alertBar: text => errors.push(text), T: text => text});
  vm.runInContext(extract('const slimIcon =', 'const TOUR_STEPS ='), context);
  vm.runInContext('savePrefs();S.prefs={...S.prefs,theme:"light"};savePrefs()', context);
  await new Promise(setImmediate);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].theme, 'dark');
  release({ok: true});
  await vm.runInContext('prefsQ', context);
  assert.equal(calls[1].theme, 'light');
  assert.deepEqual(errors, ['disk full']);
});
test('all dictionaries cover direct translation keys and preserve placeholders', () => {
  const literal = String.raw`(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")`;
  const keys = new Set();
  for (const m of html.matchAll(new RegExp(String.raw`\bT\(\s*(${literal})`, 'g'))) keys.add(vm.runInNewContext(m[1]));
  for (const m of html.matchAll(new RegExp(String.raw`\bTn\([^,]+,\s*(${literal})\s*,\s*(${literal})`, 'g'))) {
    keys.add(vm.runInNewContext(m[1]));
    keys.add(vm.runInNewContext(m[2]));
  }
  const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]);
  for (const [lang, dict] of Object.entries(dictionaries)) {
    assert.deepEqual(Object.keys(dict).sort(), Object.keys(dictionaries.en).sort(), lang);
    for (const key of keys) assert.ok(Object.hasOwn(dict, key), lang + ': ' + key);
    for (const [key, value] of Object.entries(dict)) {
      const expected = placeholders(key);
      for (const n of [0, 1, 2, 5]) {
        const rendered = typeof value === 'function' ? value(Object.fromEntries(expected.map(k => [k, n]))) : value;
        assert.equal(typeof rendered, 'string', lang + ': ' + key);
        assert.ok(placeholders(rendered).every(k => expected.includes(k)), lang + ': ' + key);
        if (n > 1) assert.deepEqual(placeholders(rendered).sort(), expected.sort(), lang + ': ' + key);
      }
    }
  }
});
test('backend error labels and dynamic error prefixes exist in every dictionary', () => {
  const literal = String.raw`(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")`;
  const keys = new Set(vm.runInNewContext(extract('const PY_MSG =', 'function trErr') + ';PY_MSG'));
  for (const file of ['app.py', 'assistant_local.py', 'assistant_library.py']) {
    const source = fs.readFileSync(path.join(__dirname, file), 'utf8');
    for (const match of source.matchAll(new RegExp(String.raw`(?:ValueError\(\s*|error=)(${literal})`, 'g'))) {
      let key = vm.runInNewContext(match[1]);
      key = key.replace(/: (?:%s)?$/, '').replace(/^Prova da %d progetti/, 'Prova da {n} progetti');
      if (key === 'Risposta HTTP ' || key === 'Il provider ha risposto con HTTP ') key += '{code}';
      if (/\p{L}/u.test(key) && key !== 'Unexpected JSON type') keys.add(key);
    }
  }
  for (const [lang, dict] of Object.entries(dictionaries)) for (const key of keys) assert.ok(Object.hasOwn(dict, key), lang + ': ' + key);
});
