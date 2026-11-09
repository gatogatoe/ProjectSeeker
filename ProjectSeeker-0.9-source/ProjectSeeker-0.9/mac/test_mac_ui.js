// Copyright (C) 2026 Gato
// SPDX-License-Identifier: GPL-3.0-only
// Licensed under the GNU General Public License v3.0; see LICENSE.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const html = fs.readFileSync(__dirname + '/ui/index.html', 'utf8');
const extract = (start, end) => html.slice(html.indexOf(start), html.indexOf(end, html.indexOf(start)));
function ui(platform) {
  const context = vm.createContext({navigator: {platform}, T: (text, values) => values ? text.replace(/\{(\w+)\}/g, (_, key) => values[key]) : text});
  vm.runInContext(extract('const IS_MAC =', 'const S =') + extract('const GENERIC =', 'const whyOf ='), context);
  return code => vm.runInContext(code, context);
}
test('Mac volumes and Windows-origin paths remain distinct', () => {
  const run = ui('MacIntel');
  assert.equal(run('SEP'), '/');
  assert.equal(run('driveOf("/Volumes/My Music/Beat.flp")'), 'My Music');
  assert.equal(run('driveOff("/Volumes/My Music/Beat.flp",new Set())'), true);
  assert.equal(run('driveOff("/Volumes/My Music/Beat.flp",new Set(["MY MUSIC"]))'), false);
  assert.equal(run('whereOf("C:/Users/Producer/kick.wav","/Users/Test",new Set())'), 'Percorso di Windows');
  assert.equal(run('whereOf("/Volumes/My Music/kick.wav","/Users/Test",new Set())'), 'Disco My Music non collegato');
  assert.equal(run('isOtherPc("/Users/Other/kick.wav","/Users/Test",new Set())'), true);
  assert.equal(run('isOtherPc("/Users/Test/kick.wav","/Users/Test",new Set())'), false);
  assert.equal(run('isOtherPc("Z:/Kits/kick.wav","/Users/Test",new Set())'), true);
});
test('Windows paths retain their existing separators', () => {
  const run = ui('Win32');
  assert.equal(run('SEP'), '\\');
  assert.equal(run('driveOf("D:/Beat.flp")'), 'D:');
  assert.equal(run('driveOff("D:/Beat.flp",new Set(["C"]))'), true);
  assert.equal(run('driveOff("D:/Beat.flp",new Set(["D"]))'), false);
});
