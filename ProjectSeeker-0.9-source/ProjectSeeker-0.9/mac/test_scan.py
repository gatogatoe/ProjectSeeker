# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""
Project Seeker - scan test, on temporary folders only.

Damaged files, a file that blocks its reader, a reader that dies, cloud-only files, long paths, odd names, sample paths of every
kind, reading only what changed. Nothing outside the temporary folder is written and no real project is opened.

    python test_scan.py            all the checks
    python test_scan.py --demo     also reads the demo projects installed with FL Studio (read only), to see that real files of
                                   every version still come through without errors
"""
import glob, json, os, shutil, sys, tempfile, time
import app

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(HERE, 'test')
bad = []


def check(name, ok, detail=''):
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else '   ' + repr(detail)))
    if not ok:
        bad.append(name)


def _slow_job(path):
    # stands in for a file that blocks its reader
    if 'blocks' in path:
        time.sleep(60)
    return dict(ok=True, r=dict(name=os.path.basename(path)))


def _dying_job(path):
    if 'dies' in path:
        os._exit(3)
    return dict(ok=True, r=dict(name=os.path.basename(path)))


def fake_flp(path, samples=(), version='26.1.0.1', bpm=140):
    sys.path.insert(0, TEST)
    from make_edge_flp import body, common, ev, u16
    import struct
    e = common(version, bpm)
    for s in samples:
        e += ev(64, struct.pack('<H', 0)) + ev(196, u16(s))
    with open(app._ext(path), 'wb') as f:
        f.write(body(e + ev(99)))


def by_name(rows):
    return {r['name']: r for r in rows}


def t_readers(tmp):
    paths = [os.path.join(tmp, n) for n in ('a.flp', 'blocks.flp', 'b.flp', 'c.flp')]
    t = time.time()
    got = app.read_many(paths, timeout=1.5, job=_slow_job, readers=2)
    took = time.time() - t
    check('a file that blocks is stopped, the others are read', got[paths[1]].get('code') == 'timeout' and all(got[p]['ok'] for p in paths if p != paths[1]), got)
    check('the limit is respected (%.1f s)' % took, took < 20, took)
    paths = [os.path.join(tmp, n) for n in ('a.flp', 'dies.flp', 'b.flp')]
    got = app.read_many(paths, job=_dying_job, readers=1)
    check('a reader that dies costs only its file', got[paths[1]].get('code') == 'crash' and got[paths[0]]['ok'] and got[paths[2]]['ok'], got)
    check('nothing to read: no reader started', app.read_many([]) == {})


def t_edge_files(tmp):
    lib = os.path.join(tmp, 'lib')
    os.makedirs(lib)
    for f in glob.glob(os.path.join(TEST, '*.flp')):
        shutil.copy(f, lib)
    rows = by_name(app.scan_root(lib))
    names = [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(TEST, '*.flp'))]
    check('every file has a row, backups apart', len(rows) == len([n for n in names if not app.BACKUP_RE.match(n)]), len(rows))
    one, two = rows['edge_copy_one'], rows['edge_copy_two']
    check('two identical files have the same mark', one['hc'] == two['hc'], (one['hc'], two['hc']))
    check('backups go to their project, newest first', one['backups'] == 2 and len(one['bk']) == 2 and one['bk'][0][2] >= one['bk'][1][2] and not two.get('bk'), one.get('bk'))
    for name, code in (('edge_empty', 'empty'), ('edge_only_header', 'no_data'), ('edge_not_flp', 'not_flp'), ('edge_no_data', 'no_data'), ('edge_garbage_after_header', 'no_data')):
        check('%s: not read, reason %s' % (name, code), rows[name].get('ec') == code and rows[name]['error'], rows[name].get('ec'))
    r = rows['edge_bad_header_length']
    check('damaged header length: still read', not r['error'] and r['bpm'] == 140, r)
    r = rows['edge_cut_in_half']
    check('cut file: what is there is kept', not r['error'] and r['partial'] and r['bpm'] == 140, r)
    r = rows['edge_very_old_fl9']
    check('FL 9: read, old text decoded', not r['error'] and any('càssa' in s['p'] for s in r['samples']), r)
    r = rows['edge_very_new_fl99']
    check('FL 99: read and marked', not r['error'] and r['bpm'] == 140 and 'new_version' in r.get('warn', ()), r)
    r = rows['edge_no_version']
    check('no version: the rest is kept', not r['error'] and r['bpm'] == 90, r)
    r = rows['edge_odd_values']
    check('absurd tempo, time and date: left empty, the rest is kept', r['bpm'] is None and r['hours'] is None and not r['created'] and r.get('title') == 'Still Here' and len(r['samples']) == 1 and {'bpm', 'created'} <= set(r.get('warn', ())), r)
    check('a scale outside the list is not a key', not r.get('key'), r.get('key'))
    r = rows['edge_info_key_patterns']
    check('title and artist', r.get('title') == 'Night Drive' and r.get('artist') == 'Someone', r)
    check('key saved by FL', r.get('key') == 'D# Minor' and r.get('kf') == 'fl', r.get('key'))
    check('patterns and channels', r['pat'] == 3 and r['chn'] == 3, (r['pat'], r['chn']))
    check('generators and effects apart', r['gen'] == ['FLEX', 'Serum'] and r['fx'] == ['Fruity Limiter', 'Pro-Q'], (r['gen'], r['fx']))
    check('the same content gives the same mark', r['hc'] and r['hc'] != rows['edge_odd_values']['hc'])
    strano = [n for n in rows if n.startswith('edge_nome strano')]
    check('odd name: read', strano and not rows[strano[0]]['error'] and '🎵' in rows[strano[0]]['name'], strano)
    r = rows['fl26_1_template_image_line']
    check('real file of FL 26: no title, no key', not r.get('title') and not r.get('key') and r['fx'] == ['Emphasizer'], r.get('title'))
    json.dumps(list(rows.values()))


def t_versions(tmp):
    lib = os.path.join(tmp, 'versions')
    a, b, other = os.path.join(lib, 'album'), os.path.join(lib, 'copia'), os.path.join(lib, 'Export')
    for d in (a, b, other, os.path.join(a, 'Backup')):
        os.makedirs(d)
    fake_flp(os.path.join(a, 'notte nera.flp'), [os.path.join(a, 'used.wav')])
    fake_flp(os.path.join(b, 'notte nera.flp'), [os.path.join(a, 'used.wav')])
    fake_flp(os.path.join(a, 'Project_12.flp'))
    fake_flp(os.path.join(a, 'Backup', 'notte nera.flp'), bpm=90)
    big = b'x' * (1024 * 1024 + 10)
    for path, data in ((os.path.join(a, 'used.wav'), big), (os.path.join(other, 'Notte Nera master.wav'), big), (os.path.join(other, 'notte.wav'), b'x' * 10),
                       (os.path.join(other, 'kick nera.wav'), big), (os.path.join(other, 'Project_12.wav'), big), (os.path.join(other, 'Project_120.wav'), big), (os.path.join(a, 'notte nera finale.mp3'), big)):
        with open(path, 'wb') as f:
            f.write(data)
    rows = app.scan_root(lib)
    r = {(os.path.basename(x['dir']), x['name']): x for x in rows}
    first, second = r['album', 'notte nera'], r['copia', 'notte nera']
    check('same project in two folders: same mark', first['hc'] == second['hc'] and first['hc'])
    check('a file in the Backup folder is not a project', len(rows) == 3 and first['backups'] == 1, len(rows))
    ex = {e[0]: e[2] for e in first['exports']}
    check('export in the folder, with its score', 'notte nera finale.mp3' in ex and ex['notte nera finale.mp3'] >= 90, first['exports'])
    check('a file the project uses is not an export', 'used.wav' not in ex, ex)
    far = {os.path.basename(e[0]): e[2] for e in first.get('exo', [])}
    check('export elsewhere: name and date', 'Notte Nera master.wav' in far, first.get('exo'))
    check('too small or a different name: left out', 'notte.wav' not in far and 'kick nera.wav' not in far, far)
    far12 = {os.path.basename(e[0]) for e in r['album', 'Project_12'].get('exo', [])}
    check('a name like Project_12 needs the whole name', 'Project_12.wav' in far12 and 'kick nera.wav' not in far12, far12)
    old, now = 1000000000, 1000000000 + 86400
    check('the score counts the date', app.export_score('beat one', 'beat one', old, now) > app.export_score('beat one', 'beat one', old, old + 86400 * 400))
    check('the score counts the folder', app.export_score('a b', 'a b', old, old, same_folder=True) > app.export_score('a b', 'a b', old, old))
    check('never a certainty above the scale', app.export_score('a', 'a', old, old, same_folder=True) == 100)


def t_fake_library():
    a, b = app.fake_library(300), app.fake_library(300)
    check('the made-up library is always the same', a == b)
    json.dumps(a)
    check('it has copies, backups and files not read', any(x.get('bk') for x in a) and len({x['hc'] for x in a}) < 300, len({x['hc'] for x in a}))


def t_samples(tmp):
    lib = os.path.join(tmp, 'samples')
    proj = os.path.join(lib, 'beat')
    os.makedirs(os.path.join(proj, 'Audio'))
    os.makedirs(os.path.join(proj, 'sub'))
    user = os.path.join(tmp, 'userdata')
    os.makedirs(os.path.join(user, 'FL Studio', 'Projects', 'old', 'Audio'))
    for rel in ('Audio\\rel.wav', 'sub\\moved.wav'):
        open(os.path.join(proj, rel), 'wb').write(b'x')
    open(os.path.join(user, 'FL Studio', 'pack.wav'), 'wb').write(b'x')
    absolute = os.path.join(tmp, 'abs.wav')
    open(absolute, 'wb').write(b'x')
    fake_flp(os.path.join(proj, 'beat.flp'), ['Audio\\rel.wav', absolute, 'C:\\gone\\moved.wav', 'C:\\gone\\lost.wav', '%FLStudioUserData%\\pack.wav', '%FLStudioFactoryData%\\none.wav', 'bare.wav'])
    keep = app._shared_data
    app._shared_data = lambda: user
    try:
        row = app.scan_root(lib)[0]
    finally:
        app._shared_data = keep
    s = {os.path.basename(x['p']): x for x in row['samples']}
    check('relative to the project folder: found', s['rel.wav']['e'] and s['rel.wav']['l'] and os.path.isabs(s['rel.wav']['p']), s['rel.wav'])
    check('absolute: found', s['abs.wav']['e'] and not s['abs.wav'].get('r'), s['abs.wav'])
    check('same name in the project folder: found by name, marked', s['moved.wav']['e'] and s['moved.wav']['l'] and s['moved.wav'].get('r'), s['moved.wav'])
    check('nowhere: missing', not s['lost.wav']['e'], s['lost.wav'])
    check('FL variable: resolved', s['pack.wav']['e'], s['pack.wav'])
    check('FL variable, file not there: missing', not s['none.wav']['e'], s['none.wav'])
    check('a bare name that is not there: missing', not s['bare.wav']['e'], s['bare.wav'])


def t_cache(tmp):
    lib = os.path.join(tmp, 'cache')
    os.makedirs(lib)
    fake_flp(os.path.join(lib, 'one.flp'))
    fake_flp(os.path.join(lib, 'two.flp'))
    open(os.path.join(lib, 'broken.flp'), 'wb').write(b'not a project')
    calls = []
    real = app.read_many

    def spy(paths, *a, **k):
        calls.append(sorted(os.path.basename(p) for p in paths))
        return real(paths, *a, **k)

    app.read_many = spy
    try:
        first = app.scan_root(lib)
        second = app.scan_root(lib, prev=first)
        check('nothing changed: nothing is read again', calls[-1] == [], calls[-1])
        check('the data stays the same', [dict(r, mt=0) for r in first] == [dict(r, mt=0) for r in second])
        fake_flp(os.path.join(lib, 'two.flp'), bpm=99)
        os.utime(os.path.join(lib, 'two.flp'), (time.time() + 5, time.time() + 5))
        third = by_name(app.scan_root(lib, prev=second))
        check('only the changed file is read', calls[-1] == ['two.flp'] and third['two']['bpm'] == 99, calls[-1])
        fourth = app.scan_root(lib, prev=list(third.values()))
        check('a file not read is not read at every scan', calls[-1] == [] and by_name(fourth)['broken']['ec'] == 'not_flp', calls[-1])
        app.scan_root(lib, prev=fourth, retry=True)
        check('retry reads it again', calls[-1] == ['broken.flp'], calls[-1])
        old = [dict(r, pv=app.PARSER - 1) for r in fourth]
        app.scan_root(lib, prev=old)
        check('a new reader reads everything once', calls[-1] == ['broken.flp', 'one.flp', 'two.flp'], calls[-1])
    finally:
        app.read_many = real


def t_cloud(tmp):
    import ctypes
    lib = os.path.join(tmp, 'cloud')
    os.makedirs(lib)
    new, seen = os.path.join(lib, 'new.flp'), os.path.join(lib, 'seen.flp')
    fake_flp(new)
    fake_flp(seen, bpm=77)
    first = [r for r in app.scan_root(lib) if r['name'] == 'seen']
    for p in (new, seen):
        ctypes.windll.kernel32.SetFileAttributesW(p, 0x1000)  # marked as "not on this PC", as a cloud provider does
    calls = []
    real = app.read_many
    app.read_many = lambda paths, *a, **k: (calls.append(list(paths)), real(paths, *a, **k))[1]
    try:
        rows = by_name(app.scan_root(lib, prev=first))
    finally:
        app.read_many = real
        for p in (new, seen):
            ctypes.windll.kernel32.SetFileAttributesW(p, 0x80)
    check('cloud-only: never opened', calls == [[]], calls)
    check('cloud-only, new: not read, with the reason', rows['new'].get('ec') == 'cloud', rows['new'].get('ec'))
    check('cloud-only, already read: keeps its data', rows['seen']['bpm'] == 77 and not rows['seen']['error'], rows['seen'])
    again = by_name(app.scan_root(lib, prev=list(rows.values())))
    check('once on the PC it is read', again['new']['bpm'] == 140 and not again['new']['error'], again['new'])


def t_long_paths(tmp):
    lib = os.path.join(tmp, 'long')
    deep = lib
    while len(deep) < 300:
        deep = os.path.join(deep, 'una cartella con un nome lungo')
    os.makedirs(app._ext(deep))
    wav = os.path.join(deep, 'kick.wav')
    with open(app._ext(wav), 'wb') as f:
        f.write(b'x' * 10)
    proj = os.path.join(deep, 'lungo.flp')
    fake_flp(proj, [wav])
    with open(app._ext(os.path.join(deep, 'export finale.wav')), 'wb') as f:
        f.write(b'x' * 10)
    rows = app.scan_root(lib)
    check('project past 260 characters: found and read', len(rows) == 1 and not rows[0]['error'] and rows[0]['bpm'] == 140 and len(rows[0]['path']) > 260, rows and rows[0].get('error'))
    check('its sample too', rows and rows[0]['samples'][0]['e'], rows and rows[0]['samples'])
    check('and its export', rows and rows[0]['exports'] and rows[0]['exports'][0][0] == 'export finale.wav', rows and rows[0]['exports'])
    check('paths come back ordinary', rows and not rows[0]['path'].startswith('\\\\?\\'), rows and rows[0]['path'][:8])
    shutil.rmtree(app._ext(lib))


def t_odd_name(tmp):
    lib = os.path.join(tmp, 'odd')
    os.makedirs(lib)
    name = 'bad\udc80name.flp'  # legal on Windows, not valid text
    fake_flp(os.path.join(lib, name))
    rows = app.scan_root(lib)
    check('a name that is not valid text: read', len(rows) == 1 and not rows[0]['error'], rows)
    out = os.path.join(tmp, 'x.json')
    app._save_json(out, dict(projects=rows))
    check('and it can be saved', app._load_json(out, {})['projects'][0]['name'] == rows[0]['name'])


def t_keys():
    cases = [('beat 140 Am', 'A minor'), ('beat_Am_140', 'A minor'), ('I Am Here', ''), ('Am', ''), ('Dm 150', 'D minor'), ('F#m', 'F# minor'), ('Bbm', 'Bb minor'),
             ('C minor loop', 'C minor'), ('c minor', 'C minor'), ('Gmaj', 'G major'), ('Eb major', 'Eb major'), ('La minore', 'A minor'), ('sol# min', 'G# minor'), ('Do maggiore', 'C major'),
             ('Project_12', ''), ('Dimitri', ''), ('Elements', ''), ('Fmaj7', ''), ('Gamma', ''), ('Bm', 'B minor'), ('a minor problem', 'A minor')]
    wrong = [(n, app.key_from_name(n), k) for n, k in cases if app.key_from_name(n) != k]
    check('keys in names (%d cases)' % len(cases), not wrong, wrong)
    check('the name wins over the folder', app.key_from_name('beat Dm', 'kit Am_') == 'D minor')
    check('the folder counts if the name says nothing', app.key_from_name('beat', 'in C minor') == 'C minor')


def t_live(tmp):
    from pathlib import Path
    from unittest.mock import patch
    import gzip
    lib = Path(tmp, 'Live')
    lib.mkdir()
    sample = lib / 'Samples' / 'Imported' / 'Kick.wav'
    sample.parent.mkdir(parents=True)
    sample.write_bytes(b'kick')
    (lib / 'Ableton Project Info').mkdir()
    sets = lib / 'Sets'
    sets.mkdir()
    project = sets / 'Song.ALS'
    def ref(name):
        return ('<SampleRef><FileRef><RelativePathType Value="3"/><RelativePath Value="Samples/Imported/' + name +
                '"/><Path Value="Z:/OldProject/' + name + '"/></FileRef></SampleRef>')
    xml = ('<Ableton Creator="Ableton Live 12.1"><LiveSet><MainTrack><DeviceChain><Mixer><Tempo><Manual Value="122.5"/>'
           '</Tempo></Mixer></DeviceChain></MainTrack><Tracks><AudioTrack><Name><EffectiveName Value="Drums"/></Name>'
           + ref('Kick.wav') * 2 + ref('Missing.wav') + '</AudioTrack></Tracks></LiveSet></Ableton>')
    project.write_bytes(gzip.compress(xml.encode()))
    fake_flp(str(lib / 'Beat.flp'))
    (lib / 'Missing.wav').write_bytes(b'unrelated')
    (lib / 'broken.als').write_bytes(b'not gzip')
    (lib / 'Backup').mkdir()
    (lib / 'Backup' / 'old.als').write_bytes(project.read_bytes())
    rows = by_name(app.scan_root(str(lib)))
    live = rows['Song']
    check('mixed library identifies both DAWs and skips Live backups',
          set(rows) == {'Beat', 'Song', 'broken'} and live['daw'] == 'Ableton Live' and rows['Beat']['daw'] == 'FL Studio')
    check('damaged Live set is reported', rows['broken']['ec'] == 'no_data')
    check('Live version, tempo and track names', (live['version'], live['bpm'], live['tracks']) == ('12.1', 122.5, ['Drums']))
    check('moved Live project resolves collected audio, deduplicates references and ignores unrelated names',
          len(live['samples']) == 2 and live['samples'][0]['p'] == str(sample) and live['samples'][0]['l'] and not live['samples'][1]['e'])
    sample.unlink()
    cached = by_name(app.scan_root(str(lib), prev=list(rows.values())))['Song']
    check('cached set rechecks sample availability', cached['tracks'] == ['Drums'] and not any(s['e'] for s in cached['samples']))
    api = app.Api.__new__(app.Api)
    api._known = lambda _: True
    with patch('os.startfile', create=True) as launch:
        check('Live set opens with its Windows association', api.open_project(str(project))['ok'])
        launch.assert_called_once_with(str(project))
        launch.side_effect = OSError()
        with patch.object(app, '_fl_exe', side_effect=AssertionError):
            check('missing Live association gives a Live-specific error', '.als' in api.open_project(str(project))['error'])


def t_reviver_collisions(tmp):
    from unittest.mock import patch
    from pathlib import Path
    kits = Path(tmp) / 'kits'
    for name, content in [('Kit A', b'aaaa'), ('Kit B', b'bbbb')]:
        folder = kits / name
        folder.mkdir(parents=True)
        (folder / 'Kick.wav').write_bytes(content)
    entries = sum((app._source_files(str(kits / name)) for name in ('Kit A', 'Kit B')), [])
    take, unsure, _ = app.match_sources(['Kit B/Kick.wav'], entries)
    check('equal size, different contents: original kit wins', take == [('Kit B/Kick.wav', 1)])
    take, unsure, _ = app.match_sources(['Kick.wav'], entries)
    check('ambiguous kick requires a choice', not take and len(unsure) == 1)
    with patch.object(app, 'reviver_dir', return_value=str(Path(tmp) / 'revived')):
        first = app.copy_source(entries[0], 'Kick.wav')
        second = app.copy_source(dict(entries[1], top=entries[0]['top']), 'Kick.wav')
        check('same-size destination collision keeps both sounds', Path(first).read_bytes() == b'aaaa' and Path(second).read_bytes() == b'bbbb')
    (kits / 'Kit B' / 'Kick.wav').write_bytes(b'aaaa')
    check('identical files can be matched automatically', bool(app.match_sources(['Kick.wav'], entries)[0]))


def t_partial_scan(tmp):
    from unittest.mock import patch
    import threading
    lib = os.path.join(tmp, 'partial')
    hidden = os.path.join(lib, 'hidden')
    os.makedirs(hidden)
    fake_flp(os.path.join(hidden, 'keep.flp'))
    store = app.Store.__new__(app.Store)
    store.state = dict(projects=[], paths=[], scanned={})
    store.lock = threading.RLock()
    store.file = os.path.join(tmp, 'partial.json')
    store.scan(lib)
    def deny(root, onerror):
        onerror(PermissionError(13, 'denied', hidden))
        yield root, [], []
    with patch.object(app, '_walk', deny):
        store.scan(lib, retry=True)
    check('unreadable subtree retains previous projects and reports path',
          len(store.state['projects']) == 1 and store.state['inaccessible'][lib] == [hidden])
    before = open(store.file, 'rb').read()
    event = threading.Event()
    try:
        store.scan(lib, lambda *_: event.set(), cancel=event)
    except app.ScanCancelled:
        pass
    check('cancelled scan leaves the saved library intact', event.is_set() and before == open(store.file, 'rb').read())
    os.remove(os.path.join(hidden, 'keep.flp'))
    store.scan(lib)
    check('successful retry clears the warning and reconciles deletions',
          not store.state['inaccessible'] and not store.state['projects'])


def t_demo():
    files = [f for base in glob.glob(r'C:\Program Files\Image-Line\FL Studio*') for f in glob.glob(os.path.join(base, '**', '*.flp'), recursive=True)]
    if not files:
        print('no demo projects here')
        return
    t = time.time()
    got = app.read_many(files)
    took = time.time() - t
    wrong = [(os.path.basename(p), g.get('code')) for p, g in got.items() if not g['ok'] or not g['r']['clean'] or g['r']['warn']]
    check('%d demo projects of FL Studio read in %.1f s' % (len(files), took), not wrong, wrong[:5])
    t = time.time()
    for f in files:
        app.parse_flp(f)
    print('     one at a time: %.1f s' % (time.time() - t))


def main():
    tmp = tempfile.mkdtemp(prefix='ps_scan_')
    keep = app.fl_index, app._plugin_list
    app.fl_index = lambda *a: {}  # FL's folders of this PC have no part in these checks
    app._plugin_list = lambda: set()
    try:
        t_reviver_collisions(tmp)
        t_partial_scan(tmp)
        t_live(tmp)
        t_keys()
        t_readers(tmp)
        t_edge_files(tmp)
        t_versions(tmp)
        t_fake_library()
        t_samples(tmp)
        t_cache(tmp)
        t_cloud(tmp)
        t_long_paths(tmp)
        t_odd_name(tmp)
        if '--demo' in sys.argv:
            t_demo()
    finally:
        app.fl_index, app._plugin_list = keep
        shutil.rmtree(app._ext(tmp), ignore_errors=True)
    print('\n%d failed' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
