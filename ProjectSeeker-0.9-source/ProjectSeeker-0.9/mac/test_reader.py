# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""
Project Seeker - .flp reader test.

Reads every .flp in test/ and compares what it extracts (version, BPM, date, time, samples, plugins, samples inside plugins,
channels, plugin paths, complete read) with test/<name>.json. If the .json is missing it is created: check it by hand the first time.
It shows right away if a change to the reader, or a new FL version, silently breaks something
(event 0xAC has already changed twice).

    python test_reader.py            compare
    python test_reader.py --new      rewrite all the .json files (after checking that the differences are right)

The .flp files are opened read only. test/ should hold small projects saved by each FL version (20, 21, 24, 25, 26),
plus the fake ones from test/make_fake_flp.py.
"""
import os, sys, json
import app

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = os.path.join(HERE, 'test')


def summary(path):
    r = app.parse_flp(path)
    return dict(clean=r['clean'], version=r['version'], bpm=r['bpm'], created=r['created'],
                hours=None if r['hours'] is None else round(r['hours'], 2),
                samples=r['samples'], native=r['native'], vst=r['vst'], plugsamples=[list(x) for x in r['plugsamples']],
                channels=r['channels'], vstpaths=r['vstpaths'], gen=r['gen'], fx=r['fx'], patterns=r['patterns'], nchannels=r['nchannels'],
                title=r['title'], artist=r['artist'], key=r['key'], warn=r['warn'])


def main():
    renew = '--new' in sys.argv
    files = sorted(f for f in os.listdir(TEST) if f.lower().endswith('.flp')) if os.path.isdir(TEST) else []
    if not files:
        print('No .flp in test/. Create the fake ones with: python test/make_fake_flp.py')
        return 1
    bad = 0
    for f in files:
        path = os.path.join(TEST, f); js = os.path.splitext(path)[0] + '.json'
        try:
            got = summary(path)
        except app.NotRead as e:
            got = dict(error=e.code)
        except Exception as e:
            got = dict(error=type(e).__name__ + ': ' + str(e))
        if renew or not os.path.exists(js):
            with open(js, 'w', encoding='utf-8') as o:
                json.dump(got, o, ensure_ascii=False, indent=1)
            print('NEW  %s  (check %s)' % (f, os.path.basename(js)))
            continue
        with open(js, encoding='utf-8') as i:
            want = json.load(i)
        diff = [k for k in sorted(set(want) | set(got)) if want.get(k) != got.get(k)]
        if diff:
            bad += 1
            print('DIFFERENT  %s' % f)
            for k in diff:
                print('   %s: expected %r, read %r' % (k, want.get(k), got.get(k)))
        else:
            print('ok  %s  (FL %s%s)' % (f, got.get('version', '?'), '' if got.get('clean', True) else ', partly read'))
    print('\n%d files, %d different' % (len(files), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
