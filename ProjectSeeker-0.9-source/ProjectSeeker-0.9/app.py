# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""
Project Seeker - READ-ONLY library of FL Studio projects.

Run:        python app.py
Test:       python app.py --dump "C:\\folder\\projects"   (prints the data read, no window)

Guarantees:
  - .flp files and samples are only opened for reading ('rb') or just checked (does it exist? how big is it?);
  - the app writes only to its own data folder: %APPDATA%\\ProjectSeeker
    (libreria.json = chosen folders and last scan, prefs.json = UI preferences,
    meta.json = favourites, tags, notes and names given in the app, ascolti.json = how many times and when each project
    was listened to in the app, album.json = albums and playlists made in the app (lists of projects),
    diario.json = notes, names and states given in Reviver, log.txt = errors,
    covers\\ = copies of the images the user picked as project covers; the original image is only read,
    Reviver\\ = copies of the sounds the user dropped in Reviver; the originals are only read);
  - outside that folder, one thing only and only when the user asks in Reviver: the Reviver folder is added to, or removed from,
    FL Studio's list of folders where it looks for sounds, in the registry.
"""
import pathlib
import copy
import os, sys, re, json, struct, datetime, glob, subprocess, webbrowser, urllib.parse
import threading, logging, logging.handlers, secrets, mimetypes, http.server, socketserver, hashlib, shutil, time, html, zlib, zipfile, difflib, unicodedata, random
import assistant_local
import assistant_library

APP = 'ProjectSeeker'
VERSION = '0.9'
PARSER = 7
DIR_MAX = 4  # as in the UI: with more than 4 projects in one folder, loose audio files are not attributed to all of them
READ_TIMEOUT = 30  # seconds for one .flp before its reader is stopped
BOOT_TIMEOUT = 60  # seconds for a reader to start: an antivirus can hold a new process for a long time
READERS_MAX = 6
FLP_MAX = 512 * 1024 * 1024  # real projects are far smaller: a bigger file with this extension isn't loaded in memory
FL_NEWEST = 26  # newest FL Studio the reader was checked against
CLOUD_ATTRS = 0x1000 | 0x40000 | 0x400000  # FILE_ATTRIBUTE_OFFLINE, _RECALL_ON_OPEN, _RECALL_ON_DATA_ACCESS: opening it would download it
LONG_PATH = 240  # Windows' ordinary calls stop at 260 characters, 248 for a folder
log = logging.getLogger(APP)
# FL 26 adds the date: "beat (overwritten on 19.10.2026 at 23h00)"; older versions: "beat (overwritten at 23h00)"
BACKUP_RE = re.compile(r'^(.*) \((?:overwritten|autosaved) (?:on [^)]* )?at [^)]*\)(?:_\d+)?$', re.I)
VAR_RE = re.compile(r'^%([A-Za-z]+)%[\\/]*(.*)$')
# system folders at the root of a drive: the Recycle Bin holds deleted projects and samples ($R1A2B3C.flp), not the library
SKIP_DIRS = {'$recycle.bin', 'recycler', 'system volume information'}


SYS_LANGS = {0x10: 'it', 0x0C: 'fr', 0x07: 'de'}  # Windows primary language ids of the app's languages (others: English)


def sys_lang():
    try:
        import ctypes
        return SYS_LANGS.get(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF, 'en')
    except Exception:
        import locale
        loc = (locale.getlocale()[0] or '').lower()
        return next((v for v in SYS_LANGS.values() if loc.startswith(v) or loc.startswith({'it': 'italian', 'fr': 'french', 'de': 'german'}[v])), 'en')


# ------------------------------------------------------------------ long paths
def _ext(p):
    """The same path in Windows' extended form, which has no length limit."""
    if os.name != 'nt' or p.startswith('\\\\?\\'):
        return p
    p = os.path.abspath(p)
    return '\\\\?\\UNC\\' + p[2:] if p.startswith('\\\\') else '\\\\?\\' + p


def _plain(p):
    if p.startswith('\\\\?\\UNC\\'):
        return '\\\\' + p[8:]
    return p[4:] if p.startswith('\\\\?\\') else p


def _lp(p):
    # only long paths are changed: every other path keeps working as it always did
    return _ext(p) if len(p) >= LONG_PATH else p


def _walk(root, onerror=None):
    """os.walk that also enters folders past the length limit, giving back ordinary paths. A folder it can't open is logged."""
    for dp, dn, fn in os.walk(_ext(root), onerror=onerror or (lambda e: log.warning('folder not read: %s', e))):
        yield _plain(dp), dn, fn


# ------------------------------------------------------------------ .flp reader
class NotRead(Exception):
    """A file that can't be read. code says why (the UI needs it), the message is shown to the user and translated there."""
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


READ_ERRORS = dict(
    empty='file vuoto', not_flp='non è un file FLP', no_data='file rovinato, nessun dato leggibile', big='file troppo grande per essere un progetto',
    timeout='lettura fermata perché troppo lunga', crash='lettura interrotta da un errore', denied='file bloccato o senza permesso di lettura',
    gone='file non trovato', cloud='solo nel cloud, non scaricato', other='errore durante la lettura')


def _not_read(code):
    return NotRead(code, READ_ERRORS[code])


def _os_reason(e):
    if isinstance(e, PermissionError):
        return 'denied'
    if isinstance(e, FileNotFoundError):
        return 'gone'
    # 358-397: the Windows errors of cloud files (provider not running, download failed...)
    return 'cloud' if 358 <= (getattr(e, 'winerror', 0) or 0) <= 397 else 'other'


def _flp_bytes(path):
    try:
        with open(_lp(path), 'rb') as f:  # READ ONLY
            head = f.read(4)
            if not head:
                raise _not_read('empty')
            if head != b'FLhd':
                raise _not_read('not_flp')
            if os.fstat(f.fileno()).st_size > FLP_MAX:
                raise _not_read('big')
            return head + f.read()
    except OSError as e:
        raise _not_read(_os_reason(e)) from e


# FL 25+: event 0xAC is no longer a fixed DWORD. Seen in real files: 3 bytes (header, FL 25.2 and 26.1) and 5 bytes
# (before the time event, FL 26.1); 7 in the files of a PyFLP fork. An event with its own length always follows it.
AC_LENS = (4, 3, 5, 2, 6, 7, 8, 1, 0)


def read_events(b):
    if b[:4] != b'FLhd' or len(b) < 8:
        raise ValueError('non è un file FLP')
    hlen = struct.unpack_from('<I', b, 4)[0]
    p = 8 + hlen
    if b[p:p + 4] != b'FLdt':
        p = b.find(b'FLdt', 8, 4096)  # a damaged header length: the data may still be right after it
    if p < 0 or len(b) < p + 8:
        raise ValueError('intestazione FLdt mancante')
    dlen = struct.unpack_from('<I', b, p + 4)[0]
    p += 8
    full = p + dlen  # where the data ends according to the header; a truncated file (interrupted save) ends earlier
    end = min(len(b), full)
    # the version (event 199) is always the first event: 0xAC has a free length only from FL 25 on
    new_ac = True
    if p + 2 < end and b[p] == 199:
        try:
            new_ac = int(b[p + 2:p + 2 + b[p + 1]].split(b'.')[0]) >= 25
        except ValueError:
            pass

    def run(p):
        # reads events from p until the end, a 0xAC to decide (FL 25+) or a cut: (events, what stopped it, position)
        out = []
        while p < end:
            i = b[p]; o = p; p += 1
            if i < 64:
                n = 1
            elif i < 128:
                n = 2
            elif i < 192:
                if i == 0xAC and new_ac:
                    return out, 'ac', o
                n = 4
            else:
                n = 0; sh = 0
                while True:
                    if p >= end:
                        return out, 'cut', o
                    c = b[p]; p += 1
                    n |= (c & 0x7f) << sh; sh += 7
                    if not c & 0x80:
                        break
            if p + n > end:
                return out, 'cut', o  # cut inside an event: keep the complete ones
            out.append((i, b[p:p + n])); p += n
        return out, 'end', p

    def lengths(o):
        # lengths to try for the 0xAC at o: first those followed by an event with its own length (or the end)
        q = o + 1
        fits = [n for n in AC_LENS if q + n <= end]
        good = [n for n in fits if q + n == full or (q + n < end and b[q + n] >= 0xC0)]
        return good + [n for n in fits if n not in good]

    # At every 0xAC the most likely length is taken; if the file then does not end exactly where the header says,
    # the other lengths are tried (going back from the last 0xAC). A truncated file can never end right,
    # so for it the first reading is kept, as "partial".
    ev = []; stack = []; dead = set(); first = None; tries = 0
    while True:
        out, why, q = run(p)
        ev += out
        if why == 'end' and q == full:
            return ev, True
        if why == 'ac':
            ns = [n for n in lengths(q) if q + 1 + n not in dead]
            if ns:
                stack.append([q, ns, 0, len(ev)])
                ev.append((0xAC, b[q + 1:q + 1 + ns[0]])); p = q + 1 + ns[0]
                continue
        if first is None:
            first = ev[:]
            if len(b) < full:
                return first, False
        while stack:  # go back to the last 0xAC with a length still to try
            fr = stack[-1]; o, ns, k, at = fr
            dead.add(o + 1 + ns[k])
            k += 1; tries += 1
            while k < len(ns) and o + 1 + ns[k] in dead:
                k += 1
            if k < len(ns) and tries <= 40:
                fr[2] = k; del ev[at:]
                ev.append((0xAC, b[o + 1:o + 1 + ns[k]])); p = o + 1 + ns[k]
                break
            stack.pop()
        else:
            return first, False


def _txt(d, uni):
    # 'replace': a damaged character costs that character, not the whole name
    return (d.decode('utf-16-le', 'replace') if uni else d.decode('latin-1')).rstrip('\0')


VST_STATE, VST_NAME, VST_PATH, VST_VENDOR = 53, 54, 55, 56


def _vst_parts(d):
    # the data FL keeps for a VST, as numbered blocks
    for start in (4, 8, 12, 16, 0):
        p = start; got = {}
        while p + 12 <= len(d):
            cid, ln = struct.unpack_from('<IQ', d, p)
            if cid > 200 or ln > len(d):
                break
            got[cid] = d[p + 12:p + 12 + ln]; p += 12 + ln
        if VST_NAME in got or VST_PATH in got or VST_VENDOR in got:
            return got
    return {}


def _vst_text(parts, cid):
    return parts.get(cid, b'').decode('utf-8', 'replace').rstrip('\0')


def _text_field(b):
    # a fixed-size text field: up to the first NUL, and only if it is really text
    s = b.split(b'\0', 1)[0].decode('utf-8', 'replace').strip()
    return s if s and all(c.isprintable() and c != '�' for c in s) else ''


# Serum's first compressed block has fixed fields at these offsets (the same in every Serum project seen, old and new):
# the file names of the two wavetables and of the noise, the preset name and its author
SERUM_TABLE_A, SERUM_TABLE_B, SERUM_NOISE, SERUM_PRESET, SERUM_AUTHOR, SERUM_END = 15368, 15880, 16392, 18800, 18848, 18896
ZLIB_MARKS = (b'\x78\x01', b'\x78\x9c', b'\x78\xda')


def _serum_info(st):
    for o in sorted(q for q in (st.find(m, 0, 512) for m in ZLIB_MARKS) if q >= 0):
        z = zlib.decompressobj()
        try:
            x = z.decompress(st[o:], 1 << 20)
        except zlib.error:
            continue
        if z.eof and len(x) >= SERUM_END:
            break
    else:
        return {}
    rel = lambda a, b: re.sub(r'^[\\/]+', '', _text_field(x[a:b])).replace('/', '\\')
    # a small length field comes just before the preset name, so the name doesn't always start at the same byte
    m = re.search(rb'[\x20-\x7e][\x20-\x7e\x80-\xff]+', x[SERUM_PRESET:SERUM_AUTHOR])
    info = dict(ps=_text_field(m.group()) if m else '', au=_text_field(x[SERUM_AUTHOR:SERUM_END]),
                sr=dict(a=rel(SERUM_TABLE_A, SERUM_TABLE_B), b=rel(SERUM_TABLE_B, SERUM_NOISE), n=rel(SERUM_NOISE, SERUM_NOISE + 512),
                        e=1 if len(z.unused_data) > 64 else 0))  # e: wavetable data saved inside the project too
    info['sr'] = {k: v for k, v in info['sr'].items() if v}
    return {k: v for k, v in info.items() if v}


def _vital_info(st):
    info = {}
    for key, short in ((rb'preset_name', 'ps'), (rb'author', 'au')):
        m = re.search(rb'"' + key + rb'":"((?:[^"\\]|\\.)*)"', st)
        if m:
            info[short] = json.loads(b'"' + m.group(1) + b'"')
    return {k: v for k, v in info.items() if v}


def _addictive_keys_info(st):
    m = re.search(rb'ExploreFile = "([^"]{1,120})"', st)
    if not m:
        return {}
    name = re.sub(r'\.Explore$', '', m.group(1).decode('utf-8', 'replace'))
    return dict(ps=re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name))


def _arcade_info(st):
    names = []
    for m in re.findall(rb'<info name="([^"]{1,80})"', st):
        n = html.unescape(m.decode('utf-8', 'replace'))
        if n not in names:
            names.append(n)
    return dict(ps=', '.join(names[:3])) if names else {}


def _flex_info(d):
    # fixed fields, the same in every FLEX channel seen (FL 24 to 26)
    info = dict(pk=_text_field(d[16:272]), ps=_text_field(d[1041:1297]))
    return {k: v for k, v in info.items() if v}


def _fl_keys_info(d):
    m = re.match(rb'[\x20-\x7e]{2,}', d[5:69])  # the name isn't always followed by a NUL
    return dict(ps=m.group().decode('ascii').strip()) if m else {}


SYNTH_READERS = {'serum': _serum_info, 'vital': _vital_info, 'addictive keys': _addictive_keys_info, 'arcade': _arcade_info,
                 'flex': _flex_info, 'fl keys': _fl_keys_info}


def _synth_info(name, st):
    """Preset name and sound files from a synth's saved data, where they can be read (ps preset, au author, pk pack, sr files
    of Serum). Each synth has its own format and a new version may change it, so anything unexpected only means "not read"."""
    read = SYNTH_READERS.get(name.lower())
    try:
        return read(st) if read else {}
    except Exception as e:
        log.info('%s data not read: %s', name, e)
        return {}


# audio file paths stored inside the data of a native plugin (FPC, Slicex, DirectWave...): event 196 does not list them
PLUG_AUDIO_RE = re.compile(r'(?:[A-Za-z]:[\\/]|\\\\|%[A-Za-z]+%[\\/])[^\x00-\x1f"<>|*?]{1,400}?\.(?:wav|mp3|flac|aiff?|ogg|wv)(?![A-Za-z0-9])', re.I)


AUDIO_MARKS = [e for x in (b'.wav', b'.mp3', b'.flac', b'.aif', b'.ogg', b'.wv') for e in (x, b'\0'.join(bytes([c]) for c in x))]


def _plugin_paths(d):
    # quick check before the real search (~25 ms per 300 KB): almost no plugin contains an audio extension
    low = d.lower()
    if not any(m in low for m in AUDIO_MARKS):
        return []
    out = []
    texts = [d.decode('latin-1')]
    for off in (0, 1):  # UTF-16 text: try both alignments
        texts.append(d[off:len(d) - (len(d) - off) % 2].decode('utf-16-le', 'replace'))
    for t in texts:
        for m in PLUG_AUDIO_RE.finditer(t):
            p = m.group(0)
            if p.lower() not in (x.lower() for x in out):
                out.append(p)
    return out


CH_NEW, CH_TYPE, CH_INNER, CH_NAME, CH_FILE, CH_DATA = 64, 21, 201, 203, 196, 213
RACK_END = (98, 99, 233, 238)  # events that only come after the channel rack (in every project seen, 99 comes first)


def _channel_event(ch, i, d, uni):
    # the first of each wins: the plugin data of a channel is followed by more events of the same kind
    if i == CH_TYPE and d and 't' not in ch:
        ch['t'] = d[0]
    elif i == CH_INNER and 'in' not in ch:
        ch['in'] = _txt(d, uni)
    elif i == CH_NAME and 'nm' not in ch:
        ch['nm'] = _txt(d, uni)
    elif i == CH_FILE and 'file' not in ch:
        ch['file'] = _txt(d, uni)
    elif i == CH_DATA and 'pl' not in ch and ch.get('in'):
        if ch['in'] == 'Fruity Wrapper':
            g = _vst_parts(d); name = _vst_text(g, VST_NAME)
            ch['pl'] = name or 'VST non identificato'
            ch.update(_synth_info(name, g.get(VST_STATE, b'')))
        else:
            ch['pl'] = ch['in']
            ch.update(_synth_info(ch['in'], d))


def _finish_channels(rack, samples):
    """Channels that hold a sound: n (position in the rack, it changes when channels are moved, so it doesn't identify a
    channel), t (type), f (index of its file in samples), pl (plugin), nm (name in FL, only if it says something more than
    the file or the plugin). Empty channels and automation clips are left out."""
    at = {s: k for k, s in enumerate(samples)}
    out = []
    for c in rack:
        file, inner = c.pop('file', None), c.pop('in', '')
        if 'pl' not in c and inner and inner != 'Fruity Wrapper':
            c['pl'] = inner
        if file in at:
            c['f'] = at[file]
        elif 'pl' not in c:
            continue
        plain = os.path.splitext(_base(file))[0] if file else c.get('pl')
        if not c.get('nm') or c['nm'] == plain:
            c.pop('nm', None)
        out.append(c)
    return out


EV_TITLE, EV_ARTIST, EV_SCALE, EV_PATTERN = 194, 207, 243, 65
# what FL's Piano roll lists under View > Scale highlighting, in the order it saves them (the values below 0 are not a key)
FL_SCALES = ('Major', 'Major Bebop', 'Major Bulgarian', 'Major Hexatonic', 'Major Pentatonic', 'Major Persian', 'Major Polymode',
             'Minor Harmonic', 'Minor Hungarian', 'Minor Melodic', 'Minor', 'Minor Neapolitan', 'Minor Pentatonic', 'Minor Polymode', 'Minor Romanian',
             'Arabic', 'Bebop Dominant', 'Blues', 'Blues Nonatonic', 'Diminished', 'Dorian', 'Eastern', 'Egyptian', 'Enigmatic', 'Hirajoshi',
             'Iwato', 'Japanese Insen', 'Locrian', 'Locrian Super', 'Lydian', 'Mixolydian', 'Neapolitan', 'Phrygian', 'Phrygian Dominant',
             'Piongio', 'Prometheus', 'Whole Tone')
NOTES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
FIELD_OF_EVENT = {156: 'bpm', 66: 'bpm', 237: 'created', 196: 'samples', 199: 'version', 201: 'plugins', 213: 'plugins', EV_TITLE: 'title',
                  EV_ARTIST: 'artist', EV_SCALE: 'key', EV_PATTERN: 'patterns', CH_NEW: 'channels'}


def _major(version):
    try:
        return int(version.split('.')[0])
    except ValueError:
        return 0


def _new_result():
    return dict(clean=True, version='', bpm=None, created='', hours=None, samples=[], native=[], vst=[], plugsamples=[], channels=[], vstpaths={},
                gen=[], fx=[], patterns=0, nchannels=0, title='', artist='', key='', warn=[], hash='')


def parse_flp(path):
    """What a .flp says. Each piece of data is read on its own: one that makes no sense or can't be read is left empty and
    named in 'warn', and everything else is kept. Raises NotRead only when nothing can be read at all."""
    b = _flp_bytes(path)
    try:
        ev, clean = read_events(b)
    except (ValueError, struct.error, IndexError) as e:
        log.info('not an FLP: %s (%s)', path, e)
        raise _not_read('no_data') from e
    if not ev:
        raise _not_read('no_data')
    r = _new_result()
    r.update(clean=clean, hash=hashlib.blake2b(b, digest_size=16).hexdigest())
    uni = True; last = None; ch = None; rack = []; lastgen = False; pats = set(); bad = set()
    for i, d in ev:
        try:
            if i == CH_NEW and len(d) == 2:
                ch = dict(n=struct.unpack('<H', d)[0]); rack.append(ch)
            elif i in RACK_END:
                ch = None
            elif ch is not None:
                _channel_event(ch, i, d, uni)
            if i == CH_NEW:
                r['nchannels'] += 1
            elif i == EV_PATTERN:
                pats.add(d)  # only patterns with notes are saved: an empty one doesn't count
            elif i == 199 and not r['version']:
                r['version'] = d.decode('ascii', 'replace').rstrip('\0')
                uni = [int(x) for x in r['version'].split('.')[:2]] >= [11, 5]
            elif i == 156 and len(d) == 4:
                t = struct.unpack('<I', d)[0] / 1000
                if 1 <= t <= 1000:
                    r['bpm'] = t
                else:
                    bad.add(i)
            elif i == 66 and len(d) == 2 and not r['bpm']:
                t = struct.unpack('<H', d)[0]
                if 1 <= t <= 1000:
                    r['bpm'] = t
                else:
                    bad.add(i)
            elif i == 237 and len(d) >= 16:
                c, w = struct.unpack_from('<dd', d)
                if w == w and 0 <= w < 1e5:  # not NaN, plausible
                    r['hours'] = round(w * 24, 3)
                else:
                    bad.add(i)
                day = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=c)
                # 0 (or a date before FL existed) means "no date", not 30.12.1899
                r['created'] = day.strftime('%Y-%m-%d') if day.year >= 1990 else ''
            elif i == EV_TITLE:
                r['title'] = _txt(d, uni).strip()
            elif i == EV_ARTIST:
                r['artist'] = _txt(d, uni).strip()
            elif i == EV_SCALE and len(d) == 8:
                scale, root = struct.unpack('<ii', d)
                if 0 <= scale < len(FL_SCALES) and 0 <= root < len(NOTES):
                    r['key'] = NOTES[root] + ' ' + FL_SCALES[scale]
            elif i == 196:
                s = _txt(d, uni)
                if s and s not in r['samples']:
                    r['samples'].append(s)
            elif i == 201:
                last = _txt(d, uni); lastgen = ch is not None
                if last and last != 'Fruity Wrapper':
                    r['native'].append(last)
                    (r['gen'] if lastgen else r['fx']).append(last)
            elif i == 213 and last == 'Fruity Wrapper':
                last = None
                g = _vst_parts(d); name = _vst_text(g, VST_NAME); where = _vst_text(g, VST_PATH)
                r['vst'].append(name or 'VST non identificato')
                (r['gen'] if lastgen else r['fx']).append(name or 'VST non identificato')
                if name and where:
                    r['vstpaths'].setdefault(name, where)
            elif i == 213 and last:
                plug, last = last, None
                known = {x.lower() for x in r['samples']} | {x[0].lower() for x in r['plugsamples']}
                for p in _plugin_paths(d):
                    if p.lower() not in known:
                        r['plugsamples'].append((p, plug)); known.add(p.lower())
        except Exception as e:
            bad.add(i)
            log.info('event %d not read in %s: %s', i, path, e)
    if not (r['version'] or r['bpm'] or r['samples'] or r['native'] or r['vst']):
        raise _not_read('no_data')  # the bytes happen to look like events, but there is nothing of a project in them
    r['patterns'] = len(pats)
    try:
        r['channels'] = _finish_channels(rack, r['samples'])
    except Exception as e:
        bad.add(CH_NEW)
        log.info('channels not read in %s: %s', path, e)
    r['warn'] = sorted({FIELD_OF_EVENT.get(i, 'other') for i in bad})
    if _major(r['version']) > FL_NEWEST:
        r['warn'].append('new_version')
    return r


# plain "Am" also means "I am": alone it counts only with a separator or a BPM next to it. Names of the notes in Italian too.
_ACC = r'(?:#|♯|b|♭)?'
_KEY_WORDS = re.compile(r'(?<![A-Za-z0-9#])([A-G]' + _ACC + r')[ _-]?(minor|minore|min|major|maggiore|magg|maj)(?![A-Za-z0-9])|'
                        r'(?<![A-Za-z0-9#])([a-g])[ _-]?(minor|minore|major|maggiore)(?![A-Za-z0-9])|'
                        r'(?<![A-Za-z0-9#àèéìòù])(do|re|mi|fa|sol|la|si)(#|♯|b|♭)?[ _-]?(minore|min|maggiore|magg|maj)(?![A-Za-z0-9])', re.I)
_KEY_SHORT = re.compile(r'(?<![A-Za-z0-9#])([A-G]' + _ACC + r')m(?![A-Za-z0-9])')
_KEY_AM_OK = re.compile(r'(?:[_\-(\[]|\d\s*(?:bpm)?[ _-]*)Am(?![A-Za-z0-9])|(?<![A-Za-z0-9])Am[ _-]+\d', re.I)
_KEY_IT = dict(do='C', re='D', mi='E', fa='F', sol='G', la='A', si='B')


def _key_in(text):
    m = _KEY_WORDS.search(text)
    if m:
        if m.group(5):
            note, kind = _KEY_IT[m.group(5).lower()] + (m.group(6) or ''), m.group(7)
        else:
            note, kind = (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
        note = note[0].upper() + note[1:].replace('♯', '#').replace('♭', 'b')
        return note + (' major' if kind.lower().startswith('ma') else ' minor')
    for m in _KEY_SHORT.finditer(text):
        if m.group(0) != 'Am' or _KEY_AM_OK.search(text):
            return m.group(1).replace('♯', '#').replace('♭', 'b') + ' minor'
    return ''


def key_from_name(name, folder=''):
    """A key written in the name of the project or of its folder: only a guess, the UI says so."""
    return _key_in(name) or _key_in(folder)


# ------------------------------------------------------------------ readers side by side
# A file can block a read forever (a dead network share, a cloud file) and a thread can't be stopped: each reader is a process,
# and it is the only thing that gets killed when a file takes too long. It also lets the reading use more than one core.
def _als_value(parent, key):
    node = parent.find(key)
    return node.get('Value', '') if node is not None else ''


def parse_als(path):
    """Read the Live Set, retaining both recorded paths so cached sets can be checked after a move."""
    import gzip
    import xml.etree.ElementTree as ET
    limit = 128 * 1024 * 1024
    try:
        with gzip.open(_lp(path), 'rb') as stream:
            xml = stream.read(limit + 1)
        if len(xml) > limit:
            raise _not_read('big')
        if b'<!DOCTYPE' in xml or b'\x00' in xml:
            raise _not_read('no_data')
        root = ET.fromstring(xml)
    except (gzip.BadGzipFile, EOFError, zlib.error, ET.ParseError) as exc:
        raise _not_read('no_data') from exc
    except OSError as exc:
        raise _not_read(_os_reason(exc)) from exc
    live = root.find('LiveSet')
    if root.tag != 'Ableton' or live is None:
        raise _not_read('no_data')
    r = _new_result()
    r['hash'] = hashlib.blake2b(xml, digest_size=16).hexdigest()
    version = re.search(r'Live (\d+(?:\.\d+)*)', root.get('Creator', ''))
    r['version'] = version.group(1) if version else ''
    for master in ('MainTrack', 'MasterTrack'):
        tempo = _als_value(live, master + '/DeviceChain/Mixer/Tempo/Manual')
        if tempo:
            try:
                bpm = float(tempo)
                if 0 < bpm <= 999:
                    r['bpm'] = bpm
            except ValueError:
                pass
            break
    r['tracks'] = [_als_value(track, 'Name/EffectiveName') or _als_value(track, 'Name/UserName')
                   for track in live.findall('Tracks/*') if track.tag.endswith('Track')]
    refs = {}
    for ref in live.iterfind('.//SampleRef/FileRef'):
        absolute = _als_value(ref, 'Path')
        relative = _als_value(ref, 'RelativePath')
        name = _als_value(ref, 'Name')
        if not relative and name:
            parts = [part.get('Dir', '') for part in ref.findall('RelativePath/RelativePathElement')]
            relative = '/'.join(parts + [name])
        if not any(value.lower().endswith(AUDIO) for value in (absolute, relative)):
            continue
        refs[(_als_value(ref, 'RelativePathType'), relative, absolute)] = None
    r['refs'] = list(refs)
    return r


def _live_samples(row, refs, ex):
    folder = row['dir']
    project = folder
    for parent in (folder, *pathlib.Path(folder).parents):
        if os.path.isdir(_lp(os.path.join(parent, 'Ableton Project Info'))):
            project = str(parent)
            break
    used = set()
    seen = set()
    for kind, relative, absolute in refs:
        candidates = []
        if relative and kind in ('', '3') and not os.path.isabs(relative):
            candidates.append(os.path.normpath(os.path.join(project, relative)))
        if absolute and os.path.isabs(absolute):
            candidates.append(os.path.normpath(absolute))
        candidates = [p for p in candidates if p.lower().endswith(AUDIO)]
        found = next((p for p in candidates if ex.file(p)), None)
        try:
            size = os.path.getsize(_lp(found)) if found else 0
        except OSError:
            found, size = None, 0
        path = found or absolute or relative
        key = os.path.normcase(os.path.normpath(path))
        if key in seen:
            continue
        seen.add(key)
        row['samples'].append(dict(p=path, e=bool(found), s=size,
                                   l=bool(found and _inside(found, project))))
        if found:
            used.add(key)
    return os.path.normcase(os.path.abspath(folder)), used


def _read_job(path):
    """Never raises: what comes back must always reach the scan, which goes on with the next file."""
    try:
        reader = parse_als if path.lower().endswith('.als') else parse_flp
        return dict(ok=True, r=reader(path))
    except NotRead as e:
        return dict(ok=False, code=e.code, msg=str(e), why=str(e.__cause__ or ''))
    except MemoryError as e:
        return dict(ok=False, code='big', msg=READ_ERRORS['big'], why=repr(e))
    except Exception as e:
        return dict(ok=False, code='other', msg=READ_ERRORS['other'], why=repr(e))


def _reader(conn, job):
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal: FL may be playing
        except Exception:
            pass
    conn.send('ready')
    while True:
        try:
            path = conn.recv()
        except EOFError:
            return
        if path is None:
            return
        conn.send(job(path))


def _timed_out(code):
    return dict(ok=False, code=code, msg=READ_ERRORS[code], why='')


class ScanCancelled(Exception):
    pass


def _check_cancel(event):
    if event is not None and event.is_set():
        raise ScanCancelled()


def read_many(paths, progress=None, timeout=READ_TIMEOUT, job=_read_job, readers=None, cancel=None):
    """path -> what _read_job gives, for each path. progress(n, path) after each file. If readers can't start at all the files
    are read here, one at a time and without a time limit: slower, but the scan still works."""
    out = {}
    if not paths:
        return out
    todo = list(reversed(paths))
    live = {}  # connection -> {proc, path, since}

    def done(path, res):
        out[path] = res
        if progress:
            progress(len(out), path)

    try:
        import multiprocessing as mp
        from multiprocessing.connection import wait
        ctx = mp.get_context('spawn')

        def start():
            here, there = ctx.Pipe()
            proc = ctx.Process(target=_reader, args=(there, job), daemon=True)
            proc.start()
            there.close()
            live[here] = dict(proc=proc, path=None, since=time.monotonic(), ready=False)

        def stop(conn):
            w = live.pop(conn)
            try:
                w['proc'].terminate()
            except OSError:
                pass
            conn.close()

        want = readers or min(READERS_MAX, max(1, (os.cpu_count() or 2) - 1), 1 + len(paths) // 25)
        for _ in range(want):
            start()
        while todo or any(w['path'] for w in live.values()):
            _check_cancel(cancel)
            for conn in wait(list(live), 0.25):
                w = live[conn]
                try:
                    msg = conn.recv()
                except (EOFError, OSError):
                    if w['path']:
                        done(w['path'], _timed_out('crash'))
                    stop(conn)
                    if todo:
                        start()
                    continue
                if msg != 'ready':
                    done(w['path'], msg)
                w['ready'] = True; w['path'] = None
                if todo:
                    w['path'] = todo.pop(); w['since'] = time.monotonic()
                    conn.send(w['path'])
                else:
                    conn.send(None); live.pop(conn); conn.close()
            now = time.monotonic()
            for conn, w in list(live.items()):
                if w['path'] and now - w['since'] > timeout:
                    done(w['path'], _timed_out('timeout'))
                    stop(conn)
                    if todo:
                        start()
                elif not w['ready'] and now - w['since'] > BOOT_TIMEOUT:
                    raise RuntimeError('reader did not start')
            if todo and not live:
                start()
    except ScanCancelled:
        for conn in list(live):
            stop(conn)
        raise
    except Exception as e:
        log.warning('readers not available, reading one file at a time: %s', e)
        for conn, w in list(live.items()):
            if w['path']:
                todo.append(w['path'])
            stop(conn)
        for path in reversed(todo):
            _check_cancel(cancel)
            if path not in out:
                done(path, job(path))
    return out


# ------------------------------------------------------------------ sample paths
def _fl_installs():
    """FL Studio install folders (Program Files\\Image-Line\\FL Studio*), newest first."""
    found = []
    for base in {os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')}:
        found += [d for d in glob.glob(os.path.join(base, 'Image-Line', 'FL Studio*')) if os.path.isdir(d)]
    return sorted(found, key=os.path.getmtime, reverse=True)


def _documents():
    """The Documents folder, also when Windows keeps it somewhere else (OneDrive, another drive)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser('~'), 'Documents')


def _shared_data():
    """FL's own data folder, as FL itself records it."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Image-Line\Shared\Paths') as k:
            d = winreg.QueryValueEx(k, 'Shared data')[0]
        if isinstance(d, str) and d.strip():
            return os.path.normpath(d)
    except Exception:
        pass
    return os.path.join(_documents(), 'Image-Line')


def _fl_dirs():
    docs = _shared_data()
    installs = _fl_installs()
    return {'flstudiouserdata': [os.path.join(docs, 'FL Studio')],
            'flstudiodownloadsdata': [os.path.join(docs, 'Downloads'), os.path.join(docs, 'FL Studio', 'Downloads')],
            # factory sounds (Packs): %FLStudioFactoryData%\Data\Patches\Packs\... lives in the install folder
            'flstudiofactorydata': installs,
            # the same sounds as saved by FL 12 and older: %FLStudioData%\Patches\Packs\... = the install's Data folder
            'flstudiodata': [os.path.join(d, 'Data') for d in installs]}


def resolve(sample, project_dir, fl_dirs):
    """Paths where a sample may be. FL saves recordings and exports as
    %FLStudioUserData%\\Projects\\<project>\\...: if the project was moved,
    the file is looked for first in the folder where the project is now."""
    m = VAR_RE.match(sample)
    if not m:
        return [sample]
    var, rest = m.group(1).lower(), [x for x in re.split(r'[\\/]+', m.group(2)) if x]
    out = []
    if var == 'flstudiouserdata' and len(rest) > 2 and rest[0].lower() == 'projects':
        out.append(os.path.join(project_dir, *rest[2:]))
    for base in fl_dirs.get(var, []):
        out.append(os.path.join(base, *rest))
    if var not in fl_dirs and os.environ.get(m.group(1)):
        out.append(os.path.join(os.environ[m.group(1)], *rest))  # any other Windows variable, such as %USERPROFILE%
    return out


def _search_path(val):
    # one value of FL's "Search paths" key: C:\folder\,  or  "C:\folder with spaces\",
    p = val[1:].split('"', 1)[0] if val.startswith('"') else val.split(',', 1)[0]
    p = os.path.expandvars(p.strip())
    return os.path.normpath(p) if p else ''


def fl_search_dirs():
    """Browser extra search folders of the newest FL Studio (each version keeps its own list), read from the registry,
    only those that exist. When FL loads a project it looks there, subfolders included, for a missing sample by its name."""
    out, seen = [], set()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Image-Line') as il:
            vers, i = [], 0
            while True:
                try:
                    n = winreg.EnumKey(il, i)
                except OSError:
                    break
                i += 1
                m = re.match(r'^FL Studio (\d+)$', n)
                if m:
                    vers.append((int(m.group(1)), n))
            for _, n in sorted(vers, reverse=True):
                try:
                    k = winreg.OpenKey(il, n + r'\Search paths')
                except OSError:
                    continue
                vals, j = [], 0
                with k:
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(k, j)
                        except OSError:
                            break
                        j += 1
                        if isinstance(val, str):
                            vals.append((int(name) if name.isdigit() else 10 ** 6, val))
                for _, val in sorted(vals):
                    p = _search_path(val)
                    if p and os.path.normcase(p) not in seen and os.path.isdir(p):
                        seen.add(os.path.normcase(p)); out.append(p)
                break
    except Exception as e:
        log.info('FL search paths not read: %s', e)
    return out


_flidx = dict(t=0, dirs=None, idx={})


def fl_index(limit=400000, cancel=None):
    """Audio file name (lowercase) -> paths, in FL's extra search folders, in the order FL searches them (folder order,
    then alphabetical). Kept for two minutes: a scan of several folders lists them once. A drive root with millions of
    files stops at 'limit'."""
    dirs = fl_search_dirs()
    if _flidx['dirs'] == dirs and time.time() - _flidx['t'] < 120:
        return _flidx['idx']
    idx, n = {}, 0
    for d in dirs:
        for dp, dn, fn in _walk(d):
            _check_cancel(cancel)
            dn[:] = sorted(x for x in dn if x.lower() not in SKIP_DIRS)
            for f in sorted(fn):
                if f.lower().endswith(AUDIO):
                    idx.setdefault(f.lower(), []).append(os.path.join(dp, f)); n += 1
            if n >= limit:
                break
        if n >= limit:
            log.info('FL search folders: stopped at %d files', n)
            break
    _flidx.update(t=time.time(), dirs=dirs, idx=idx)
    return idx


def _fl_exe():
    """Installed FL Studio (the newest), if it is in the usual folders."""
    found = []
    for base in {os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')}:
        for name in ('FL64.exe', 'FL.exe'):
            found += glob.glob(os.path.join(base, 'Image-Line', 'FL Studio*', name))
    return max(found, key=os.path.getmtime) if found else None


# ------------------------------------------------------------------ scan
def _base(p):
    return re.split(r'[\\/]', p)[-1]


def _plugin_list():
    """Names of the plugins in FL's own list: a plugin moved to another folder is still on the PC, at a path older projects don't know."""
    base = os.path.join(_shared_data(), 'FL Studio', 'Presets', 'Plugin database', 'Installed')
    names = set()
    for dp, dn, fn in os.walk(base):
        names.update(os.path.splitext(f)[0].lower() for f in fn if f.lower().endswith('.fst'))
    return names


def _sound_dirs():
    """Serum's folder and the folder of FLEX's packs, if they are in the usual place. If not, nothing can be said about their files."""
    serum, flex = os.path.join(_documents(), 'Xfer', 'Serum Presets'), os.path.join(_shared_data(), 'FLEX', 'Packs')
    return serum if os.path.isdir(serum) else None, flex if os.path.isdir(flex) else None


class _Exists:
    """os.path.isfile with a per-folder cache: if the folder (or drive, or network share) is missing, all its files
    are missing without asking the disk one by one. With a \\\\NAS switched off each query can block for seconds."""
    def __init__(self):
        self.dirs = {}

    def _dir(self, d):
        k = os.path.normcase(d)
        if k not in self.dirs:
            up = os.path.dirname(d)
            self.dirs[k] = (self._dir(up) if up and up != d else True) and os.path.isdir(_lp(d))
        return self.dirs[k]

    def file(self, p):
        d = os.path.dirname(p)
        return (not d or self._dir(d)) and os.path.isfile(_lp(p))


def _check_synths(row, ex, plugins, dirs, seen):
    """vm: plugins of the project that aren't on this PC. m in a Serum channel: its files missing from Serum's folder.
    pm in a FLEX channel: its pack isn't installed. Checked at every scan, also for a project that wasn't read again.
    A Waves shell changes name with every update of Waves, so an old one says nothing."""
    serum, flex = dirs
    gone = []
    for name, where in row.get('vp', {}).items():
        if name.lower() in plugins or name.lower().startswith('waveshell'):
            continue
        if where not in seen:
            seen[where] = os.path.exists(where)
        if not seen[where]:
            gone.append(name)
    if gone:
        row['vm'] = gone
    for c in row.get('ch', ()):
        c.pop('pm', None)
        if flex and c.get('pk') and not ex.file(os.path.join(flex, c['pk'] + '.preset')):
            c['pm'] = 1
        sr = c.get('sr')
        if not sr:
            continue
        sr.pop('m', None)
        if serum:
            miss = [sr[k] for k, sub in (('a', 'Tables'), ('b', 'Tables'), ('n', 'Noises'))
                    if sr.get(k, '').lower().endswith('.wav') and not ex.file(os.path.join(serum, sub, sr[k]))]
            if miss:
                sr['m'] = miss


def _new_row(path, root, folder, stem):
    return dict(path=path, daw='Ableton Live' if path.lower().endswith('.als') else 'FL Studio', root=root, dir=folder, folder=os.path.basename(folder), name=stem, error='', partial=False,
                version='', bpm=None, created='', hours=None, samples=[], native=[], vst=[], exports=[], ch=[], vp={}, pv=PARSER)


def _check_sample(s, dp, ndp, fl_dirs, flidx, audio, ex):
    """Whether one sample of a project can be found, looking where FL looks. Returns what the library keeps of it and the file."""
    nd = os.path.join(ndp, '')  # a drive root (d:\) already ends with the separator
    found = None
    if not VAR_RE.match(s) and not os.path.isabs(s):
        s = os.path.normpath(os.path.join(dp, s))  # relative to the project folder
    for c in resolve(s, dp, fl_dirs):
        if ex.file(c):
            found = c; break
    moved = None; cands = ()
    if not found:
        # FL also looks for a missing file by name: first in the project folder and its subfolders, then in its
        # Browser extra search folders (tested with FL 26). It takes the first file with that name, right or wrong
        name = _base(s); ln = name.lower()
        here = [os.path.join(d, name) for d in audio.get(ln, ()) if d == ndp or d.startswith(nd)]
        cands = here + flidx.get(ln, [])
        for c in cands:
            if os.path.isfile(_lp(c)):
                found = moved = c; break
    try:
        size = os.path.getsize(_lp(found)) if found else 0
    except OSError:
        found = moved = None
        size = 0
    local = bool(found) and os.path.normcase(os.path.abspath(found)).startswith(nd)
    one = dict(p=s, e=bool(found), s=size, l=local)
    if moved:
        one['r'] = moved  # where it really is: FL finds it by itself
        if not local:
            one['x'] = 1  # in one of FL's extra search folders
        if len(cands) > 1:
            # more files with this name and different sizes (not just copies of one kit): FL may take another one
            sizes = set()
            for c in cands:
                try:
                    sizes.add(os.path.getsize(_lp(c)))
                except OSError:
                    pass
            if len(sizes) > 1:
                one['rn'] = len(cands)
    return one, found


def recheck_by_name(rows, names):
    """A file entering or leaving FL's extra search folders changes what FL finds for every project looking for that name, not
    only the open one. Only the samples that depend on that search are checked, without reading any .flp or project folder: a
    library can hold 20,000 projects. names: lowercase file names."""
    fl_dirs, flidx, ex = _fl_dirs(), fl_index(), _Exists()
    for row in rows:
        if row.get('daw') == 'Ableton Live':
            continue
        samples = row.get('samples') or ()
        for i, s in enumerate(samples):
            if (s.get('e') and not s.get('x')) or _base(s['p']).lower() not in names:
                continue
            one, _ = _check_sample(s['p'], row['dir'], os.path.normcase(os.path.abspath(row['dir'])), fl_dirs, flidx, {}, ex)
            if s.get('pl'):
                one['pl'] = s['pl']
            samples[i] = one


def _result_of(old):
    """The data of a project already read, without reopening the file."""
    return dict(_new_result(), refs=old.get('refs', []), tracks=old.get('tracks', []), version=old['version'], bpm=old['bpm'], created=old['created'], hours=old['hours'], native=old['native'],
                vst=old['vst'], clean=not old.get('partial'), samples=[s['p'] for s in old['samples'] if not s.get('pl')],
                plugsamples=[(s['p'], s['pl']) for s in old['samples'] if s.get('pl')], channels=copy.deepcopy(old.get('ch', [])), vstpaths=old.get('vp', {}),
                gen=old.get('gen', []), fx=old.get('fx', []), patterns=old.get('pat', 0), nchannels=old.get('chn', 0), title=old.get('title', ''),
                artist=old.get('artist', ''), key=old['key'] if old.get('kf') == 'fl' else '', warn=old.get('warn', []), hash=old.get('hc', ''))


def _stat_row(row):
    st = os.stat(_lp(row['path']))
    row['kb'] = round(st.st_size / 1024)
    row['modified'] = datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d')
    row['sz'] = st.st_size; row['mt'] = st.st_mtime
    return st


def _mark_unread(row, code, msg, why=''):
    row.update(error=msg, ec=code)
    row.setdefault('kb', 0); row.setdefault('modified', '')
    log.warning('project not read: %s (%s%s)', row['path'], code, ': ' + why if why else '')


def _plan_read(row, old):
    """Decides, without opening the file, how to get the data of a project. Returns what is already known (old row) or None
    if the file must be read. A cloud-only file is left alone; what was read from it before stays valid until it changes."""
    try:
        st = _stat_row(row)
    except OSError as e:
        code = _os_reason(e)
        _mark_unread(row, code, READ_ERRORS[code], str(e))
        return 'skip'
    same = bool(old) and old.get('sz') == st.st_size and old.get('mt') == st.st_mtime
    cloud = bool(getattr(st, 'st_file_attributes', 0) & CLOUD_ATTRS)
    if same and cloud and not old.get('error') and old.get('samples') is not None:
        row['pv'] = old.get('pv', 0)  # to be read properly once it is on this PC
        return old
    if cloud:
        _mark_unread(row, 'cloud', READ_ERRORS['cloud'])
        return 'skip'
    if same and old.get('pv') == PARSER and old.get('ec') != 'cloud':
        return old
    return None


def _read_project(row, r, fl_dirs, flidx, audio, ex, plugins, sound_dirs, seen_plugins):
    """Fills row with what the .flp says (r) and checks its samples. Returns the project folder (normcase) and the files it uses."""
    dp = row['dir']
    row.update(version=r['version'], bpm=r['bpm'], created=r['created'], hours=r['hours'],
               native=r['native'], vst=r['vst'], partial=not r['clean'], ch=r['channels'], vp=r['vstpaths'],
               gen=r['gen'], fx=r['fx'], pat=r['patterns'], chn=r['nchannels'], hc=r['hash'])
    for short, val in (('title', r['title']), ('artist', r['artist']), ('warn', r['warn'])):
        if val:
            row[short] = val
    # the key FL saves wins; one found in a name is only a guess
    key = r['key'] or key_from_name(row['name'], row['folder'])
    if key:
        row.update(key=key, kf='fl' if r['key'] else 'nome')
    if row['daw'] == 'Ableton Live':
        row.update(refs=r['refs'], tracks=r['tracks'], pat=None, chn=None)
        return _live_samples(row, r['refs'], ex)
    _check_synths(row, ex, plugins, sound_dirs, seen_plugins)
    ndp = os.path.normcase(os.path.abspath(dp))
    used = set()
    for s, plug in [(x, None) for x in r['samples']] + list(r['plugsamples']):
        one, found = _check_sample(s, dp, ndp, fl_dirs, flidx, audio, ex)
        if plug:
            one['pl'] = plug  # found inside the data of a plugin (FPC, Slicex...)
        row['samples'].append(one)
        if found:
            used.add(os.path.normcase(os.path.abspath(found)))
    return ndp, used


# ------------------------------------------------------------------ what belongs to a project: backups and possible exports
BACKUP_LIST = 30  # newest first: FL can leave hundreds of them
EXPORT_LIST = 12
EXPORT_MIN_SIZE = 1024 * 1024  # away from the project only: smaller files are one-shots, not a song
EXPORT_MIN_SCORE, EXPORT_MIN_NAME = 55, 0.6
EXPORT_TOKEN_MAX = 300  # a word shared by more files than this says nothing ("kick"): it isn't used to look for candidates
EXPORT_WORDS_SKIP = {'master', 'mastered', 'final', 'finale', 'mix', 'mixdown', 'export', 'exported', 'bounce', 'bounced', 'render', 'rendered', 'demo', 'version',
                     'ver', 'new', 'nuovo', 'nuova', 'untitled', 'project', 'progetto', 'beat', 'instrumental', 'instr', 'tag', 'tagged', 'bpm', 'wav', 'mp3', 'flac'}


def _plain_words(text):
    text = unicodedata.normalize('NFD', text)
    return re.findall(r'[^\W_]+', ''.join(c for c in text if not unicodedata.combining(c)).lower())


def _name_score(stem, audio):
    """0 to 1: how much the name of an audio file looks like the name of a project."""
    a, b = _plain_words(stem), _plain_words(audio)
    ja, jb = ''.join(a), ''.join(b)
    if not ja or not jb:
        return 0
    if ja == jb:
        return 1
    wa, wb = set(a) - EXPORT_WORDS_SKIP, set(b) - EXPORT_WORDS_SKIP
    # a name like "Project_12" says nothing with its words: only the whole name counts, at the start of the file name
    if not {w for w in wa if not w.isdigit()}:
        return 0.7 if jb.startswith(ja) else 0
    if wa <= wb:
        return 0.9
    return max(0.8 * len(wa & wb) / len(wa), 0.8 * difflib.SequenceMatcher(None, ja, jb).ratio() if len(ja) >= 4 else 0)


def _date_score(a, b):
    days = abs(a - b) / 86400
    return 25 if days <= 1 else 18 if days <= 7 else 10 if days <= 30 else 4 if days <= 180 else 0


def export_score(stem, audio, project_time, audio_time, same_folder=False, near_folder=False):
    """0 to 100, name 60, date 25, folder 15. A possible link, never a certain one: nothing inside a .flp says what was exported from it."""
    return round(60 * _name_score(stem, audio)) + _date_score(project_time, audio_time) + (15 if same_folder else 8 if near_folder else 0)


def _link_exports(pending, loose, real_dir, nproj, dir_used):
    """exports: audio files in the project folder that it doesn't use. exo: audio files elsewhere under the same chosen folder
    whose name looks like the project. Each one comes with its score."""
    used = set().union(*dir_used.values()) if dir_used else set()
    # After all projects are read: a file another project of the folder uses is not an export of this one, unless its name
    # contains this project's name (an export reused elsewhere)
    for row, dp, ndp, stem, mine_used in pending:
        many = nproj.get(ndp, 0) > DIR_MAX
        exp = []
        for fa in loose.get(ndp, ()):
            full = os.path.join(dp, fa); nf = os.path.normcase(full); mine = stem.lower() in fa.lower()
            if nf in mine_used or fa.lower().endswith(('.mid', '.midi')):
                continue
            if (many or nf in dir_used[ndp]) and not mine:
                continue
            try:
                fs = os.stat(_lp(full))
            except OSError:
                continue
            exp.append((export_score(stem, os.path.splitext(fa)[0], row.get('mt', 0), fs.st_mtime, same_folder=True), fs.st_mtime, fa, fs.st_size))
        exp.sort(key=lambda x: (x[0], x[1]), reverse=True)
        row['exports'] = [[fa, sz, sc] for sc, _, fa, sz in exp[:EXPORT_LIST]]
    # elsewhere: only the files sharing a word with a project are looked at, or 20,000 projects would compare with every file
    words = {}
    for ndp, files in loose.items():
        for fa in files:
            if not fa.lower().endswith(('.mid', '.midi')):
                base = os.path.splitext(fa)[0]
                for w in (set(_plain_words(base)) - EXPORT_WORDS_SKIP) | {''.join(_plain_words(base))}:
                    if not w.isdigit():
                        words.setdefault(w, []).append((ndp, fa))
    sizes, best = {}, {}
    for row, dp, ndp, stem, mine_used in pending:
        stem_words = (set(_plain_words(stem)) - EXPORT_WORDS_SKIP) | {''.join(_plain_words(stem))}
        cands = {c for w in stem_words if len(words.get(w, ())) <= EXPORT_TOKEN_MAX for c in words.get(w, ())}
        for nd, fa in cands:
            if nd == ndp:
                continue
            base = os.path.splitext(fa)[0]
            name = _name_score(stem, base)
            if name < EXPORT_MIN_NAME:
                continue
            full = os.path.join(real_dir[nd], fa); nf = os.path.normcase(full)
            if nf in used:
                continue
            if nf not in sizes:
                try:
                    fs = os.stat(_lp(full)); sizes[nf] = (fs.st_size, fs.st_mtime)
                except OSError:
                    sizes[nf] = (0, 0)
            size, when = sizes[nf]
            if size < EXPORT_MIN_SIZE:
                continue
            near = nd.startswith(os.path.join(ndp, '')) or ndp.startswith(os.path.join(nd, ''))
            score = export_score(stem, base, row.get('mt', 0), when, near_folder=near)
            if score >= EXPORT_MIN_SCORE:
                best.setdefault(nf, []).append((score, id(row), row, full, size))
    # a file goes to the projects it fits best, not to every project with a similar name
    links = {}
    for lst in best.values():
        top = max(x[0] for x in lst)
        for score, key, row, full, size in sorted((x for x in lst if x[0] >= top - 5), key=lambda x: -x[0])[:3]:
            links.setdefault(key, (row, []))[1].append([full, size, score])
    for row, found in links.values():
        row['exo'] = sorted(found, key=lambda x: -x[2])[:EXPORT_LIST]


def _backup_list(paths):
    """Path, size and date of a project's backups, without opening them."""
    out = []
    for p in paths:
        try:
            st = os.stat(_lp(p))
        except OSError:
            continue
        out.append([p, st.st_size, datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M')])
    out.sort(key=lambda x: x[2], reverse=True)
    return out[:BACKUP_LIST]


def scan_root(root, progress=None, prev=None, retry=False, inaccessible=None, cancel=None):
    """progress(done, total, name) is called while projects are read.
    prev: projects of the previous scan; a .flp with the same path, size and date is not read again (its samples are always
    checked again), not even one that couldn't be read: it would waste up to READ_TIMEOUT at every scan. retry reads those again."""
    root = os.path.abspath(root)
    fl_dirs = _fl_dirs()
    flidx = fl_index(400000, cancel)
    inaccessible = [] if inaccessible is None else inaccessible
    def record_error(error):
        inaccessible.append(_plain(error.filename or root))
        log.warning('folder not read: %s', error)
    prev = {os.path.normcase(p['path']): p for p in (prev or []) if not (retry and p.get('error'))}
    projects = []; backups = {}; todo = []
    audio = {}    # audio file name (lowercase) -> folders (normcase) containing it: where FL would look for it
    loose = {}    # folder -> audio files directly inside: possible exports
    real_dir = {}  # folder (normcase) -> as it is written on disk
    nproj = {}    # folder -> number of projects
    dir_used = {}  # project folder -> files used by its projects
    pending = []  # projects read without errors, waiting for their exports
    ex = _Exists()
    plugins, sound_dirs, seen_plugins = _plugin_list(), _sound_dirs(), {}
    # list the files first (fast), so the number of projects to read is known
    for dp, dn, fn in _walk(root, record_error):
        _check_cancel(cancel)
        if progress:
            progress(len(todo), 0, dp)
        dn[:] = [d for d in dn if d.lower() not in SKIP_DIRS]
        in_backup = os.path.basename(dp).lower() == 'backup'
        pdir = os.path.dirname(dp) if in_backup else dp
        ndp = os.path.normcase(dp)
        for f in sorted(fn):
            fl = f.lower()
            if fl.endswith(AUDIO):
                audio.setdefault(fl, []).append(ndp)
                loose.setdefault(ndp, []).append(f)
                real_dir[ndp] = dp
                continue
            if not fl.endswith(('.flp', '.als')):
                continue
            stem = os.path.splitext(f)[0]
            if fl.endswith('.als') and in_backup:
                continue
            m = BACKUP_RE.match(stem) if fl.endswith('.flp') else None
            if in_backup or m:
                key = (os.path.normcase(pdir), (m.group(1) if m else stem).lower())
                backups.setdefault(key, []).append(os.path.join(dp, f))
                continue
            todo.append((dp, f, stem))
            nproj[ndp] = nproj.get(ndp, 0) + 1
    plan = []; to_read = []
    for dp, f, stem in todo:
        _check_cancel(cancel)
        row = _new_row(os.path.join(dp, f), root, dp, stem)
        how = _plan_read(row, prev.get(os.path.normcase(row['path'])))
        plan.append((row, dp, stem, how))
        if how is None:
            to_read.append(row['path'])
    steps = len(to_read) + len(plan)

    def read_step(n, path):
        if progress:
            progress(n, steps, os.path.splitext(os.path.basename(path))[0])

    read = read_many(to_read, read_step, cancel=cancel)
    for i, (row, dp, stem, how) in enumerate(plan):
        _check_cancel(cancel)
        if progress:
            progress(len(to_read) + i, steps, stem)
        if how == 'skip':
            projects.append(row)
            continue
        if how is None:
            got = read[row['path']]
            if not got['ok']:
                _mark_unread(row, got['code'], got['msg'], got.get('why', ''))
                projects.append(row)
                continue
            r = got['r']
            if not r['clean'] or r['warn']:
                log.warning('partly read (FL %s, %s): %s', r['version'] or '?', ','.join(r['warn']) or 'cut', row['path'])
        elif how.get('error'):
            row.update(error=how['error'], ec=how.get('ec', 'other'))
            projects.append(row)
            continue
        else:
            r = _result_of(how)
        try:
            ndp, used = _read_project(row, r, fl_dirs, flidx, audio, ex, plugins, sound_dirs, seen_plugins)
            pending.append((row, dp, ndp, stem, used))
            dir_used.setdefault(ndp, set()).update(used)
        except Exception as e:
            _mark_unread(row, 'other', READ_ERRORS['other'], repr(e))
        projects.append(row)
    _link_exports(pending, loose, real_dir, nproj, dir_used)
    for row in projects:
        found = backups.get((os.path.normcase(row['dir']), row['name'].lower()), ()) if row['daw'] == 'FL Studio' else ()
        row['backups'] = len(found)
        if found:
            row['bk'] = _backup_list(found)
    return projects


def rescan_project(old):
    """Reads one project again, after it was saved in FL or something was copied for it. Its exports and backups stay as they
    are until the next scan."""
    audio = {}
    for d, dn, fn in _walk(old['dir']):
        dn[:] = [x for x in dn if x.lower() not in SKIP_DIRS]
        nd = os.path.normcase(d)
        for f in fn:
            if f.lower().endswith(AUDIO):
                audio.setdefault(f.lower(), []).append(nd)
    row = _new_row(old['path'], old['root'], old['dir'], old['name'])
    row['exports'], row['backups'] = old.get('exports', []), old.get('backups', 0)
    for k in ('exo', 'bk'):
        if old.get(k):
            row[k] = old[k]
    how = _plan_read(row, old)
    if how == 'skip':
        return row
    if how is None:
        got = read_many([row['path']])[row['path']]
        if not got['ok']:
            _mark_unread(row, got['code'], got['msg'], got.get('why', ''))
            return row
        r = got['r']
    elif how.get('error'):
        row.update(error=how['error'], ec=how.get('ec', 'other'))
        return row
    else:
        r = _result_of(how)
    try:
        _read_project(row, r, _fl_dirs(), fl_index(), audio, _Exists(), _plugin_list(), _sound_dirs(), {})
    except Exception as e:
        _mark_unread(row, 'other', READ_ERRORS['other'], repr(e))
    return row


# ------------------------------------------------------------------ Reviver: copies of the sounds a project misses
# FL looks for a missing sample by its name, subfolders included, in its Browser extra search folders (tested with FL 26).
# So a copy with the right name in a folder FL knows brings the sound back, and the project itself is never touched.
REVIVER, OWN_SOUNDS = 'Reviver', 'Suoni tuoi'
SOURCE_MAX, OPTIONS_MAX, OTHERS_MAX = 200000, 12, 300  # files looked at in what is dropped, shown to choose from, listed apart
SOURCE_FILE_MAX = 512 * 1024 * 1024  # a single archive member: reject ZIP bombs before copying
SOURCE_TOTAL_MAX = 2 * 1024 * 1024 * 1024  # total uncompressed audio inspected in one archive
SEARCH_SLOTS = 64  # never seen more than 31 in FL's list: a limit against filling the registry by mistake
UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
PATH_MAX = 240  # Windows' limit is 260, and FL has to open the file too


def reviver_dir():
    d = os.path.join(data_dir(), REVIVER)
    os.makedirs(d, exist_ok=True)
    return d


def _fl_versions():
    """FL Studio versions in the registry, newest first."""
    import winreg
    out = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Image-Line') as il:
        i = 0
        while True:
            try:
                n = winreg.EnumKey(il, i)
            except OSError:
                break
            i += 1
            m = re.match(r'^FL Studio (\d+)$', n)
            if m:
                out.append((int(m.group(1)), n))
    return [n for _, n in sorted(out, reverse=True)]


def fl_running():
    try:
        r = subprocess.run(['tasklist', '/NH', '/FO', 'CSV'], capture_output=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except Exception as e:
        log.info('tasklist: %s', e)
        return False
    names = r.stdout.decode('utf-8', 'replace').lower()
    return '"fl64.exe"' in names or '"fl.exe"' in names


def _search_value(d):
    p = d.rstrip('\\') + '\\'
    return '"%s",' % p if re.search(r'[ ,]', p) else p + ','


def _search_values(k):
    import winreg
    out, j = [], 0
    while True:
        try:
            name, val, _ = winreg.EnumValue(k, j)
        except OSError:
            return out
        j += 1
        out.append((name, val))


def link_folder(d):
    """Adds the folder to FL's Browser extra search folders, as one more value in the first free place. Only this value is
    written: the rest of FL's settings stay as they are. FL must be closed: it reads this list when it starts."""
    import winreg
    versions = _fl_versions()
    if not versions:
        raise OSError('FL Studio non trovato')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Software\\Image-Line\\%s\\Search paths' % versions[0], 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
        vals = _search_values(k)
        if any(isinstance(v, str) and os.path.normcase(_search_path(v)) == os.path.normcase(d) for _, v in vals):
            return versions[0]
        used = {n for n, _ in vals}
        slot = next((str(i) for i in range(SEARCH_SLOTS) if str(i) not in used), None)
        if slot is None:
            raise OSError('Le cartelle extra di FL Studio sono piene')
        winreg.SetValueEx(k, slot, 0, winreg.REG_SZ, _search_value(d))
    log.info('Reviver folder added to the search folders of %s (value %s, %d values were there)', versions[0], slot, len(vals))
    return versions[0]


def unlink_folder(d):
    import winreg
    versions = _fl_versions()
    if not versions:
        return
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Image-Line\\%s\\Search paths' % versions[0], 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
    except OSError:
        return
    with k:
        for n, v in _search_values(k):
            if isinstance(v, str) and os.path.normcase(_search_path(v)) == os.path.normcase(d):
                winreg.DeleteValue(k, n)
                log.info('Reviver folder removed from the search folders of %s (value %s)', versions[0], n)


def reviver_state():
    d = os.path.join(data_dir(), REVIVER)
    files = size = 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            try:
                size += os.path.getsize(os.path.join(dp, f)); files += 1
            except OSError:
                pass
    return dict(dir=d, linked=any(os.path.normcase(x) == os.path.normcase(d) for x in fl_search_dirs()), files=files, size=size)


def _source_files(path):
    """Audio files in what was dropped: a folder, a zip or one file. Only names and sizes: nothing is copied or extracted here.
    Raises ValueError for something else (a .rar can't be read)."""
    path = os.path.normpath(str(path)); out = []
    keep = lambda n: n.lower().endswith(AUDIO) and not n.startswith('._')
    if os.path.isdir(path):
        top = os.path.basename(path.rstrip('\\/')) or path[:1]
        for dp, dn, fn in os.walk(path):
            dn[:] = [x for x in dn if x.lower() not in SKIP_DIRS and x != '__MACOSX']
            for f in fn:
                if keep(f) and len(out) < SOURCE_MAX:
                    full = os.path.join(dp, f)
                    try:
                        out.append(dict(name=f, rel=os.path.relpath(full, path), src=full, size=os.path.getsize(full), top=top))
                    except OSError:
                        pass
    elif path.lower().endswith('.zip'):
        top = os.path.splitext(os.path.basename(path))[0]
        with zipfile.ZipFile(path) as z:
            total = 0
            for info in z.infolist():
                name = re.split(r'[\\/]', info.filename)[-1]
                if info.is_dir() or not keep(name) or '__MACOSX' in info.filename or info.flag_bits & 1:  # bit 0: password
                    continue
                if info.file_size > SOURCE_FILE_MAX:
                    raise ValueError('Archivio rifiutato: un file audio supera 512 MB')
                total += info.file_size
                if total > SOURCE_TOTAL_MAX:
                    raise ValueError('Archivio rifiutato: i file audio superano 2 GB')
                if len(out) < SOURCE_MAX:
                    out.append(dict(name=name, rel=info.filename, src=path, member=info.filename, size=info.file_size, top=top))
    elif path.lower().endswith(AUDIO) and os.path.isfile(path):
        out.append(dict(name=os.path.basename(path), rel=os.path.basename(path), src=path, size=os.path.getsize(path), top=''))
    else:
        raise ValueError(os.path.basename(path))
    return out


def _plain_name(name):
    return re.sub(r'[^a-z0-9]', '', os.path.splitext(name)[0].lower())


def _folder_score(old, rel):
    # how many of the last folders in the path the project remembers are also in this file's path
    have = {x.lower() for x in re.split(r'[\\/]+', rel)[:-1]}
    return sum(1 for x in re.split(r'[\\/]+', old)[:-1][-3:] if x.lower() in have)


def _source_digest(entry):
    if entry.get('member'):
        with zipfile.ZipFile(entry['src']) as archive, archive.open(entry['member']) as stream:
            return _digest(stream)
    with open(entry['src'], 'rb') as stream:
        return _digest(stream)


def _digest(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1 << 20), b''):
        digest.update(chunk)
    return digest.digest()


def match_sources(missing, entries):
    """Which file goes with which missing sample. take: (sample, position in entries), a sure match; unsure: several different
    files with that name and nothing to tell them apart; near: no file with that name, only similar ones."""
    by_name, by_plain = {}, {}
    for i, e in enumerate(entries):
        by_name.setdefault(e['name'].lower(), []).append(i)
        by_plain.setdefault(_plain_name(e['name']), []).append(i)
    take, unsure, near, seen = [], [], [], set()
    for s in missing:
        name = _base(s).lower()
        if name in seen:
            continue
        seen.add(name)
        found = by_name.get(name)
        if not found:
            alike = by_plain.get(_plain_name(name))
            if alike and _plain_name(name):
                near.append((s, alike[:OPTIONS_MAX]))
            continue
        if len(found) == 1:
            take.append((s, found[0])); continue
        if len({entries[i]['size'] for i in found}) == 1:
            try:
                first = _source_digest(entries[found[0]])
                if all(_source_digest(entries[i]) == first for i in found[1:]):
                    take.append((s, found[0]))
                    continue
            except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
                pass
        def score(i):
            entry = entries[i]
            return _folder_score(s, os.path.join(entry['top'], entry['rel']))
        ranked = sorted(found, key=score, reverse=True)
        a, b = score(ranked[0]), score(ranked[1])
        if a > b:
            take.append((s, ranked[0]))
        else:
            unsure.append((s, ranked[:OPTIONS_MAX]))
    return take, unsure, near


def _safe_leaf(name):
    # `name` can come from an untrusted project file via reviver_pick. On Windows,
    # joining a drive-qualified leaf (for example `C:outside.wav`) can escape root.
    name = UNSAFE_NAME.sub('_', re.split(r'[\\/]', str(name))[-1]).strip(' .')[:180]
    if not name or name in ('.', '..'):
        raise ValueError('Nome file non valido')
    if name.split('.', 1)[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        name = '_' + name
    return name


def _dest_for(e, name):
    """Where the copy goes, inside the Reviver folder and with the name FL looks for. Parts of the path come from the file
    system or from a zip: cleaned, so nothing can end up outside the folder."""
    clean = lambda x: UNSAFE_NAME.sub('_', x).strip(' .')
    name = _safe_leaf(name)
    parts = [clean(x) for x in re.split(r'[\\/]+', e['rel'])[:-1]]
    top = clean(e['top']) or OWN_SOUNDS
    parts = [x for x in parts if x]
    if parts and parts[0].lower() == top.lower():
        parts = parts[1:]
    root = reviver_dir()
    folder = os.path.join(root, top, *parts)
    if len(os.path.join(folder, name)) > PATH_MAX:
        folder = os.path.join(root, top[:60].strip(' .'))
    target = os.path.abspath(os.path.join(folder, name))
    if os.path.commonpath((os.path.abspath(root), target)) != os.path.abspath(root):
        raise ValueError('Destinazione non valida')
    return folder


def _copy_limited(source, dest, expected):
    """Copy one archive member while enforcing its declared and actual uncompressed size."""
    if expected < 0 or expected > SOURCE_FILE_MAX:
        raise ValueError('File audio troppo grande (massimo 512 MB)')
    copied = 0
    while True:
        chunk = source.read(min(1 << 20, SOURCE_FILE_MAX + 1 - copied))
        if not chunk:
            break
        copied += len(chunk)
        if copied > SOURCE_FILE_MAX or copied > expected:
            raise ValueError('Dimensione del file audio non valida')
        dest.write(chunk)
    if copied != expected:
        raise ValueError('Dimensione del file audio non valida')


def copy_source(e, name):
    """Copies one file into the Reviver folder (from a zip, it extracts only that one). A different file with the same path is
    never overwritten. Returns the path of the copy."""
    name = _safe_leaf(name)
    if e.get('member') and (e.get('size', SOURCE_FILE_MAX + 1) < 0 or e.get('size', SOURCE_FILE_MAX + 1) > SOURCE_FILE_MAX):
        raise ValueError('File audio troppo grande (massimo 512 MB)')
    folder = _dest_for(e, name)
    for n in range(1, 100):
        d = folder if n == 1 else '%s (%d)' % (folder, n)
        dest = os.path.join(d, name)
        if not os.path.exists(dest):
            break
        if os.path.getsize(dest) == e['size'] and _source_digest({'src': dest}) == _source_digest(e):
            return dest
    else:
        raise OSError('Troppi file con lo stesso nome: ' + name)
    os.makedirs(d, exist_ok=True)
    part = dest + '.part'
    try:
        if e.get('member'):
            with zipfile.ZipFile(e['src']) as z, z.open(e['member']) as i, open(part, 'wb') as o:
                _copy_limited(i, o, e['size'])
        else:
            shutil.copyfile(e['src'], part)
        os.replace(part, dest)
    except Exception:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    idx = _flidx.get('idx')
    if isinstance(idx, dict) and dest not in idx.get(name.lower(), ()):  # FL's folders are listed every two minutes: this one counts now
        idx.setdefault(name.lower(), []).append(dest)
    return dest


# ------------------------------------------------------------------ kit folders (the user's samples)
AUDIO = ('.wav', '.mp3', '.flac', '.aif', '.aiff', '.ogg', '.m4a', '.wv', '.mid', '.midi')
PLAYABLE = ('.wav', '.mp3', '.flac', '.ogg', '.m4a')  # what WebView2 can play (no AIFF)
IMAGES = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')  # project covers the user can pick
COVER_RE = re.compile(r'^[0-9a-f]{16}-[0-9a-z]{1,12}\.(?:png|jpg|webp|gif|bmp)$')  # names of the copies in covers\
COVER_MAX = 20 * 1024 * 1024
ALBUM_MAX, TRACK_MAX = 500, 1000  # albums or playlists, projects in one of them
ALBUM_ID_RE = re.compile(r'^[0-9a-z]{4,24}$')
ALBUM_KINDS = ('albums', 'playlists')
# subfolders that are categories of one kit, not separate kits (Kicks, Snares, 808, Loops...)
CATEG = re.compile(r'^[\d\s._()-]*(kicks?|snares?|claps?|snaps?|hi[\s-]?hats?|hats?|hh|oh|ch|open[\s-]?hats?|closed[\s-]?hats?|808s?|bass(es)?|subs?|'
                   r'perc(s|ussions?)?|rims?|rimshots?|toms?|cymbals?|crash(es)?|rides?|shakers?|fx|sfx|effects?|vox|vocals?|loops?|'
                   r'melod(y|ies)|one[\s-]?shots?|drums?|risers?|impacts?|transitions?|chords?|keys|midi|presets?|samples?|textures?|'
                   r'ambien(t|ce)|foley|stems?|instruments?|synths?|leads?|pads?|plucks?|guitars?|pianos?|strings?|brass|bells?|'
                   r'drum[\s-]?loops?|melodic[\s-]?loops?|bonus|extras?|misc)[\d\s._()-]*$', re.I)


def _audio_files(base, cancel=None, inaccessible=None):
    """Audio files under 'base' (relative path, size). Read only: listing and size, nothing else."""
    out, stack = [], [base]
    inaccessible = [] if inaccessible is None else inaccessible
    while stack:
        _check_cancel(cancel)
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name.lower() not in SKIP_DIRS:
                                stack.append(e.path)
                        elif e.name.lower().endswith(AUDIO):
                            out.append([os.path.relpath(e.path, base), e.stat().st_size])
                    except OSError:
                        inaccessible.append(e.path)
        except OSError:
            inaccessible.append(d)
    return out


def scan_kits(root, progress=None, cancel=None, prev=None):
    """A kit folder: the sounds directly inside and those of each subfolder.
    'one' = looks like a single kit (the subfolders are categories like Kicks, Snares...)."""
    root = os.path.abspath(root)
    subs, rootfiles, inaccessible = [], [], []
    try:
        with os.scandir(root) as it:
            for e in it:
                _check_cancel(cancel)
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name.lower() not in SKIP_DIRS:
                            subs.append(e.name)
                    elif e.name.lower().endswith(AUDIO):
                        rootfiles.append([e.name, e.stat().st_size])
                except OSError:
                    inaccessible.append(e.path)
    except OSError:
        inaccessible.append(root)
    subs.sort(key=str.lower)
    parts = [dict(sub='', files=rootfiles)] if rootfiles else []
    for i, sub in enumerate(subs):
        if progress:
            progress(i, len(subs), sub)
        parts.append(dict(sub=sub, files=_audio_files(os.path.join(root, sub), cancel, inaccessible)))
    inaccessible = list(dict.fromkeys(inaccessible))
    if inaccessible:
        by_sub = {os.path.normcase(pt['sub']): pt for pt in parts}
        known = {os.path.normcase(os.path.join(root, pt['sub'], f[0])) for pt in parts for f in pt['files']}
        for pt in (prev or {}).get('parts', []):
            for file in pt['files']:
                full = os.path.normcase(os.path.join(root, pt['sub'], file[0]))
                if full in known or not any(full == os.path.normcase(p) or _inside(full, p) for p in inaccessible):
                    continue
                key = os.path.normcase(pt['sub'])
                if key not in by_sub:
                    by_sub[key] = dict(sub=pt['sub'], files=[])
                    parts.append(by_sub[key])
                by_sub[key]['files'].append(list(file))
                known.add(full)
        subs = list(dict.fromkeys(subs + [pt['sub'] for pt in parts if pt['sub']]))
        for path in inaccessible:
            log.warning('kit path not read, previous data retained: %s', path)
    cat = sum(1 for x in subs if CATEG.match(x))
    one = (not subs) or cat * 2 >= len(subs)
    return dict(scanned=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), one=one, parts=parts, inaccessible=inaccessible)


# ------------------------------------------------------------------ app state
def data_dir():
    base = os.environ.get('APPDATA') or os.path.join(os.path.expanduser('~'), '.config')
    d = os.path.join(base, APP)
    os.makedirs(d, exist_ok=True)
    return d


def covers_dir():
    # copies of the cover images, named <hash of the project path>-<time>.<ext>: a new pick gets a new name (no stale cache)
    d = os.path.join(data_dir(), 'covers')
    os.makedirs(d, exist_ok=True)
    return d


def _drives():
    """Letters of the drives connected now (Windows). Used to say "drive G: not connected" instead of "missing"."""
    try:
        import ctypes
        m = ctypes.windll.kernel32.GetLogicalDrives()
        return [chr(65 + i) for i in range(26) if m >> i & 1]
    except Exception:
        return []


def _inside(path, folder):
    """True if path is inside folder. A drive root (D:\\) already ends with the separator: adding another one never matched."""
    return os.path.normcase(path).startswith(os.path.normcase(folder).rstrip('\\/') + os.sep)


DIARY_STATES = ('miss', 'ok', 'swap', 'lost')
DIARY_BRANCHES = ('dr', 'ba', 'me', 'vo', 're', 'sy', 'fx', 'al')
TEXT_MAX, NAME_MAX, DIARY_ITEMS = 4000, 120, 2000


def _clean_diary(d):
    """What is kept of one project's diary. nodes: {channel key: name, note, st (state), br (branch), preset}; br: {branch:
    name, note, open}; steps: the user's own steps; log: {d: date, t: text, own: written by hand}. Empty values are left out."""
    if not isinstance(d, dict):
        return {}
    text = lambda v, n: str(v or '').strip()[:n]

    def node(x):
        if not isinstance(x, dict):
            return {}
        o = {k: text(x.get(k), n) for k, n in (('name', NAME_MAX), ('note', TEXT_MAX), ('preset', NAME_MAX))}
        if x.get('st') in DIARY_STATES:
            o['st'] = x['st']
        if x.get('br') in DIARY_BRANCHES:
            o['br'] = x['br']
        return {k: v for k, v in o.items() if v}

    out = {}
    nodes = {str(k)[:700]: node(v) for k, v in list((d.get('nodes') or {}).items())[:DIARY_ITEMS]} if isinstance(d.get('nodes'), dict) else {}
    out['nodes'] = {k: v for k, v in nodes.items() if v}
    br = {}
    if isinstance(d.get('br'), dict):
        for k, v in d['br'].items():
            if k in DIARY_BRANCHES and isinstance(v, dict):
                e = {f: text(v.get(f), n) for f, n in (('name', NAME_MAX), ('note', TEXT_MAX))}
                if isinstance(v.get('open'), bool):
                    e['open'] = v['open']
                e = {f: x for f, x in e.items() if x != ''}
                if e:
                    br[k] = e
    out['br'] = br
    steps = []
    if isinstance(d.get('steps'), list):
        for s in d['steps'][:DIARY_ITEMS]:
            e = node(s)
            if isinstance(s, dict) and re.fullmatch(r'[0-9a-z]{1,16}', str(s.get('id') or '')):
                steps.append(dict(e, id=s['id']))
    out['steps'] = steps
    log_ = []
    if isinstance(d.get('log'), list):
        for e in d['log'][:DIARY_ITEMS]:
            if isinstance(e, dict) and text(e.get('t'), TEXT_MAX) and re.fullmatch(r'\d{4}-\d\d-\d\d', str(e.get('d') or '')):
                x = dict(d=e['d'], t=text(e['t'], TEXT_MAX))
                if e.get('own'):
                    x['own'] = 1
                log_.append(x)
    out['log'] = log_
    # file name (lowercase) -> the copy made in the Reviver folder, and the name of the user's own sound put there
    for k in ('copied', 'own'):
        if isinstance(d.get(k), dict):
            out[k] = {str(a)[:300]: text(b, 700) for a, b in list(d[k].items())[:DIARY_ITEMS] if text(b, 700)}
    return {k: v for k, v in out.items() if v}


ROW_DETAIL = ('ch', 'vp', 'refs')  # for one project at a time: too much to send to the UI with the whole library


def _row_public(p):
    q = p.copy()
    for k in ROW_DETAIL:
        q.pop(k, None)
    return q


def _load_json(path, default):
    """Reads a JSON file of the data folder. If it is corrupt it is set aside (name.rotto-date.json) instead of being
    overwritten by the next save: nothing is lost and it can be recovered by hand."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding='utf-8-sig') as f:
            v = json.load(f)
        if not isinstance(v, type(default)):
            raise ValueError('Unexpected JSON type')
        return v
    except Exception as e:
        bad = os.path.splitext(path)[0] + '.rotto-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.json'
        if os.path.exists(bad):
            bad = os.path.splitext(bad)[0] + '-' + secrets.token_hex(8) + '.json'
        try:
            os.replace(path, bad)
            log.error('%s damaged (%s): set aside as %s', path, e, bad)
        except OSError:
            log.error('%s damaged (%s) and could not be moved', path, e)
        return default


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _save_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)  # escaped, not as UTF-8: Windows allows file names that UTF-8 can't write
    os.replace(tmp, path)


def _clean_albums(data, old):
    """Albums and playlists as the UI sends them, checked: ids, names, track lists (project paths). A project goes in
    one album only (the first one that has it), in any number of playlists. The cover is kept from the stored copy: it
    changes only through choose_album_image / remove_album_image."""
    out = {k: [] for k in ALBUM_KINDS}
    covers = {}
    for k in ALBUM_KINDS:
        for x in old[k] if isinstance(old.get(k), list) else []:
            if isinstance(x, dict) and isinstance(x.get('id'), str) and isinstance(x.get('cover'), str):
                covers[k, x['id']] = x['cover']
    ids, in_album = set(), set()
    for k in ALBUM_KINDS:
        for a in (data.get(k) or [])[:ALBUM_MAX] if isinstance(data.get(k), list) else []:
            i = str(a.get('id') or '') if isinstance(a, dict) else ''
            if not ALBUM_ID_RE.match(i) or i in ids:
                continue
            ids.add(i)
            tracks = []
            for t in (a.get('tracks') or [])[:TRACK_MAX] if isinstance(a.get('tracks'), list) else []:
                if not isinstance(t, str) or not t.strip():
                    continue
                t = os.path.normcase(t)
                if t in tracks or (k == 'albums' and t in in_album):
                    continue
                tracks.append(t)
                if k == 'albums':
                    in_album.add(t)
            e = dict(id=i, name=str(a.get('name') or '').strip()[:120] or 'Album', tracks=tracks)
            desc = str(a.get('desc') or '').strip()[:2000]
            if desc:
                e['desc'] = desc
            rel = str(a.get('release') or '')
            if k == 'albums' and re.match(r'^\d{4}-\d\d-\d\d$', rel):
                e['release'] = rel
            if covers.get((k, i)):
                e['cover'] = covers[(k, i)]
            out[k].append(e)
    out['dur'] = old.get('dur') if isinstance(old.get('dur'), dict) else {}
    return out


def _album_covers(albums):
    return {x.get('cover') for k in ALBUM_KINDS for x in (albums.get(k) or []) if isinstance(x, dict) and x.get('cover')}


class Store:
    def __init__(self):
        d = data_dir()
        self.file = os.path.join(d, 'libreria.json')
        self.pfile = os.path.join(d, 'prefs.json')
        self.mfile = os.path.join(d, 'meta.json')
        self.afile = os.path.join(d, 'ascolti.json')
        self.bfile = os.path.join(d, 'album.json')
        self.dfile = os.path.join(d, 'diario.json')
        # one save at a time: pywebview runs each call in its own thread (e.g. preferences during a scan)
        self.lock = threading.RLock()
        self.state = dict(paths=[], scanned={}, containers=[], pins=[], prefs={}, kitpaths=[], kitlib={}, kitmode={}, projects=[])
        self.state.update(_load_json(self.file, {}))
        # preferences and notes in separate files: a click on theme or colour doesn't rewrite the whole library
        prefs = _load_json(self.pfile, {}) if os.path.exists(self.pfile) else None
        self.state['prefs'] = prefs if isinstance(prefs, dict) else dict(self.state.get('prefs') or {})
        if prefs is None and self.state['prefs']:
            # first run with prefs.json: move the preferences from libreria.json there right away,
            # or the first library save (without preferences) would lose them
            try:
                self.save_prefs()
            except OSError as e:
                log.error('prefs.json not written: %s', e)
        self.meta = _load_json(self.mfile, {})
        # listens in the app: {normcase(project path): {"n": times, "t": "YYYY-MM-DDTHH:MM:SSZ" (UTC: no hour lost or doubled
        # when the clocks change) of the last one}}
        self.plays = _load_json(self.afile, {})
        # albums and playlists: {"albums": [...], "playlists": [...], "dur": {audio path: [seconds, size]}}
        raw = _load_json(self.bfile, {})
        self.albums = _clean_albums(raw, raw)
        # Reviver: {normcase(project path): what _clean_diary keeps}
        self.diary = _load_json(self.dfile, {})

    def save_diary(self):
        with self.lock:
            _save_json(self.dfile, self.diary)

    def save(self):
        with self.lock:
            _save_json(self.file, {k: v for k, v in self.state.items() if k != 'prefs'})

    def save_prefs(self):
        with self.lock:
            _save_json(self.pfile, self.state['prefs'])

    def save_meta(self):
        with self.lock:
            _save_json(self.mfile, self.meta)

    def save_plays(self):
        with self.lock:
            _save_json(self.afile, self.plays)

    def save_albums(self):
        with self.lock:
            _save_json(self.bfile, self.albums)

    def durations(self):
        """Durations measured by the UI, only while the file still has the same size (a new export with the same name
        is measured again)."""
        out = {}
        for k, v in list((self.albums.get('dur') or {}).items()):
            try:
                if isinstance(v, list) and len(v) == 2 and os.path.getsize(k) == v[1]:
                    out[k] = v[0]
            except OSError:
                pass
        return out

    def public(self):
        with self.lock:
            s = dict(self.state)
            s['projects'] = [_row_public(p) for p in s['projects']]
            s['meta'] = self.meta
            s['plays'] = self.plays
            s['albums'] = {k: self.albums.get(k) or [] for k in ALBUM_KINDS}
        s['albums']['dur'] = self.durations()
        s['home'] = os.path.expanduser('~')
        s['datafile'] = self.file
        s['syslang'] = sys_lang()
        s['drives'] = _drives()
        s['flpaths'] = fl_search_dirs()
        s['version'] = VERSION
        return s

    def scan_kits(self, path, progress=None, cancel=None):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise ValueError('Cartella non trovata: ' + path)
        st = self.state
        key = os.path.normcase(path)
        old = [x for x in st['kitpaths'] if os.path.normcase(x) == key]
        if old:
            path = old[0]
        data = scan_kits(path, progress, cancel, st['kitlib'].get(path))
        with self.lock:
            _check_cancel(cancel)
            st['kitlib'][path] = data
            if not old:
                st['kitpaths'].append(path)
            self.save()

    def scan(self, path, progress=None, retry=False, cancel=None):
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            raise ValueError('Cartella non trovata: ' + path)
        key = os.path.normcase(path)
        st = self.state
        with self.lock:
            prev = [p for p in st['projects'] if _inside(p['path'], path)]
        inaccessible = []
        new = scan_root(path, progress, prev, retry, inaccessible, cancel)
        new.extend(row for row in prev if any(_inside(row['path'], folder) for folder in inaccessible))
        with self.lock:
            _check_cancel(cancel)
            warnings = st.setdefault('inaccessible', {})
            if inaccessible:
                warnings[path] = inaccessible
            else:
                warnings.pop(path, None)
            # everything inside this folder is replaced (also projects of a chosen subfolder); the rest stays
            st['projects'] = [p for p in st['projects'] if not _inside(p['path'], path)] + new
            if key not in [os.path.normcase(x) for x in st['paths']]:
                st['paths'].append(path)
            st['scanned'][path] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            self.reroot()
            self.save()

    def reroot(self):
        """Each project belongs to the deepest chosen folder containing it, whatever the scan order. With nested folders
        (Projects and Projects\\Beats) removing one keeps the projects the other still contains."""
        st = self.state
        paths = sorted(st['paths'], key=lambda x: len(os.path.normcase(x).rstrip('\\/')), reverse=True)
        keep = []
        for p in st['projects']:
            r = next((x for x in paths if _inside(p['path'], x)), None)
            if r is not None:
                p['root'] = r; keep.append(p)
        st['projects'] = keep


class Api:
    def __init__(self):
        self._store = Store()
        self._window = None
        self._scan_lock = threading.Lock()
        self._cancel = threading.Event()
        self._prog = dict(active=False)
        self._full = False
        self._rv_sources = []  # audio files of what was last dropped in Reviver: the UI refers to them by position
        self._rv_ok = set()  # those files (normcase): they can be played and dragged, though they aren't in the library

    def assistant_config(self):
        return assistant_local.read_config(data_dir())

    def assistant_chats(self):
        with self._store.lock:
            chats = _load_json(os.path.join(data_dir(), 'chat.json'), [])
            return [c for c in chats if isinstance(c, dict) and re.fullmatch(r'[0-9a-f]{32}', str(c.get('id') or '')) and isinstance(c.get('title'), str) and isinstance(c.get('updated'), str) and isinstance(c.get('messages'), list) and all(isinstance(m, dict) and m.get('role') in ('user', 'assistant') and isinstance(m.get('content'), str) and isinstance(m.get('projects', []), list) and all(isinstance(p, dict) and isinstance(p.get('path'), str) and isinstance(p.get('name'), str) for p in m.get('projects', [])) for m in c['messages'])]

    def assistant_chat_save(self, chat_id, messages):
        if not isinstance(messages, list) or not messages:
            return dict(ok=False, error='Conversazione non valida')
        clean = []
        for message in messages:
            if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant') or not isinstance(message.get('content'), str):
                return dict(ok=False, error='Messaggio non valido')
            entry = dict(role=message['role'], content=message['content'])
            if message['role'] == 'user' and message.get('mode') in ('search', 'inspiration', 'wrapped'):
                entry['mode'] = message['mode']
                if entry['mode'] == 'wrapped':
                    kind = message.get('wrapped_kind') or 'both'
                    if kind not in ('listening', 'projects', 'both'):
                        return dict(ok=False, error='Tipo di Wrapped non valido')
                    entry['wrapped_kind'] = kind
                    try:
                        entry['wrapped_period'] = assistant_library.wrapped_period(message.get('wrapped_period'))
                    except ValueError as e:
                        return dict(ok=False, error=str(e))
            selected = str(message.get('project_context') or '')
            if selected and self._known(selected):
                entry['project_context'] = selected
            if isinstance(message.get('wrapped'), dict):
                entry['wrapped'] = message['wrapped']
            if message.get('error'):
                entry['error'] = True
            if message.get('cancelled'):
                entry['cancelled'] = True
            if isinstance(message.get('projects'), list):
                entry['projects'] = [dict(name=str(p.get('name') or ''), path=str(p.get('path') or '')) for p in message['projects'] if isinstance(p, dict) and p.get('path')]
            clean.append(entry)
        if not any(m['role'] == 'user' for m in clean):
            return dict(ok=False, error='Conversazione non valida')
        chat_id = str(chat_id or '')
        if chat_id and not re.fullmatch(r'[0-9a-f]{32}', chat_id):
            return dict(ok=False, error='Conversazione non valida')
        try:
            with self._store.lock:
                path = os.path.join(data_dir(), 'chat.json')
                chats = _load_json(path, [])
                if chat_id and not any(isinstance(c, dict) and c.get('id') == chat_id for c in chats):
                    return dict(ok=False, error='Conversazione non trovata')
                chat_id = chat_id or secrets.token_hex(16)
                first = next(m['content'] for m in clean if m['role'] == 'user')
                chat = dict(id=chat_id, title=' '.join(first.split())[:100], updated=_utc_now(), messages=clean)
                chats = [chat] + [c for c in chats if isinstance(c, dict) and c.get('id') != chat_id]
                _save_json(path, chats)
            return dict(ok=True, chat=chat)
        except OSError:
            return dict(ok=False, error='Impossibile salvare la conversazione')

    def assistant_chat_delete(self, chat_id):
        if not re.fullmatch(r'[0-9a-f]{32}', str(chat_id or '')):
            return dict(ok=False, error='Conversazione non valida')
        try:
            with self._store.lock:
                path = os.path.join(data_dir(), 'chat.json')
                chats = _load_json(path, [])
                _save_json(path, [c for c in chats if isinstance(c, dict) and c.get('id') != chat_id])
            return dict(ok=True)
        except OSError:
            return dict(ok=False, error='Impossibile eliminare la conversazione')

    def assistant_save(self, config):
        try:
            if not isinstance(config, dict):
                raise ValueError('Configurazione non valida')
            return dict(ok=True, config=assistant_local.save_config(data_dir(), config))
        except (OSError, ValueError) as e:
            return dict(ok=False, error=str(e))

    def assistant_status(self, request_id):
        with self._store.lock:
            state = getattr(self, '_assistant_state', {})
            return dict(state) if state.get('id') == request_id else {}

    def assistant_stop(self, request_id):
        with self._store.lock:
            generation = getattr(self, '_assistant_requests', {}).get(request_id)
        if generation:
            generation.cancel()
        return dict(ok=bool(generation))

    def assistant_chat(self, message, history=None, selected_path='', request_id='', task='', period=None, language='', wrapped_kind=None):
        generation = assistant_local.Generation() if request_id else None
        if generation:
            with self._store.lock:
                if not hasattr(self, '_assistant_requests'):
                    self._assistant_requests = {}
                self._assistant_requests[request_id] = generation
        def update(text='', reasoning=False, stage='answer'):
            if generation:
                generation.check()
            if request_id:
                with self._store.lock:
                    self._assistant_state = dict(id=request_id, text=text, stage='reasoning' if reasoning else stage)
        progress = update if request_id else None
        options = dict(progress=progress, generation=generation) if generation else {}
        if language:
            options['language'] = language
        try:
            assistant_local.response_language(language)
            if wrapped_kind not in (None, 'listening', 'projects', 'both'):
                raise ValueError('Tipo di Wrapped non valido')
            if task not in ('', 'chat', 'search', 'inspiration', 'wrapped'):
                raise ValueError('Modalità assistente non valida')
            period = assistant_library.wrapped_period(period) if task == 'wrapped' else None
            update(stage='query' if task == 'search' else 'answer')
            config = assistant_local.read_config(data_dir())
            if not config['local'] and not config['share']:
                answer = assistant_local.chat(data_dir(), message, [], '', **options)
                return dict(ok=True, answer=answer, projects=[])
            if task in ('', 'chat'):
                answer = assistant_local.chat(data_dir(), message, history, '', **options)
                return dict(ok=True, answer=answer, projects=[])
            if task == 'search':
                user_history = [m for m in (history or []) if isinstance(m, dict) and m.get('role') == 'user']
                raw = assistant_local.chat(data_dir(), message, user_history, '',
                                           instruction=assistant_library.PLAN_PROMPT + datetime.date.today().isoformat(),
                                           **(dict(generation=generation, progress=lambda text, reasoning: update(reasoning=reasoning, stage='query')) if generation else {}))
                plan = assistant_library.parse_plan(raw)
                if plan['intent'] != 'search':
                    raise ValueError('Impossibile interpretare la ricerca. Prova a specificare nome, BPM, plugin o tag.')
            else:
                plan = assistant_library.parse_plan(json.dumps(dict(intent=task)))
            update(stage='search')
            with self._store.lock:
                rows = assistant_library.projects(self._store.state['projects'], self._store.meta, self._store.plays)
            context, cards = assistant_library.context(rows, plan, str(selected_path or ''), period, wrapped_kind)
            update()
            answer = assistant_local.chat(data_dir(), message, history, context, task=plan['intent'], **options)
            if generation:
                generation.check()
            return dict(ok=True, answer=answer, wrapped=json.loads(context).get('summary'), projects=[dict(name=p['name'], path=p['path']) for p in cards])
        except (assistant_local.Cancelled, OSError, ValueError, KeyError, IndexError, TypeError) as e:
            if generation and generation.event.is_set():
                return dict(ok=False, cancelled=True, answer=self.assistant_status(request_id).get('text', ''), projects=[])
            return dict(ok=False, error=str(e))
        finally:
            if generation:
                generation.cancel()
                with self._store.lock:
                    self._assistant_requests.pop(request_id, None)

    def window_maximized(self):
        from System.Windows.Forms import FormWindowState
        return self._window.native.WindowState == FormWindowState.Maximized

    def _install_window_frame(self):
        """Keep Windows' animated taskbar transitions while the web UI draws the title bar."""
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(self._window.native.Handle.ToInt64())
        user32 = ctypes.windll.user32
        controls = ctypes.windll.comctl32
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                      ctypes.c_size_t, ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_size_t)
        controls.DefSubclassProc.argtypes = proc_type._argtypes_[:4]
        controls.DefSubclassProc.restype = ctypes.c_ssize_t
        controls.SetWindowSubclass.argtypes = [wintypes.HWND, proc_type, ctypes.c_size_t, ctypes.c_size_t]
        controls.RemoveWindowSubclass.argtypes = [wintypes.HWND, proc_type, ctypes.c_size_t]

        @proc_type
        def frame_proc(handle, msg, wparam, lparam, subclass_id, data):
            if msg == 0x0083 and wparam:  # WM_NCCALCSIZE: use the title bar space for the web UI
                if user32.IsZoomed(wintypes.HWND(handle)):
                    rect = wintypes.RECT.from_address(lparam)
                    top, bottom = rect.top, rect.bottom
                    controls.DefSubclassProc(handle, msg, wparam, lparam)
                    # Keep the invisible maximized border outside the monitor work area.
                    rect.top = top + (bottom - rect.bottom)
                return 0
            if msg == 0x0082:  # WM_NCDESTROY
                controls.RemoveWindowSubclass(handle, frame_proc, subclass_id)
            return controls.DefSubclassProc(handle, msg, wparam, lparam)

        self._frame_proc = frame_proc  # keep the callback alive for the lifetime of the HWND
        self._frame_hwnd = hwnd
        if not controls.SetWindowSubclass(hwnd, frame_proc, 1, 0):
            raise OSError('Cannot install custom window frame')
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)  # SWP_FRAMECHANGED, preserve geometry and focus

    def window_command(self, action):
        if action == 'close':
            self._window.destroy()
        elif action == 'minimize':
            import ctypes
            ctypes.windll.user32.PostMessageW(self._frame_hwnd, 0x0112, 0xF020, 0)  # WM_SYSCOMMAND, SC_MINIMIZE
        elif action == 'maximize' and not self._full:
            if self.window_maximized():
                self._window.restore()
            else:
                self._window.maximize()

    def window_drag(self, edge):
        """Let Windows track the mouse while moving or sizing the frameless window."""
        import ctypes
        from System import Action
        edges = ('left', 'right', 'top', 'top-left', 'top-right', 'bottom', 'bottom-left', 'bottom-right')
        if self._full or edge not in ('move', *edges):
            return
        command = 0xF012 if edge == 'move' else 0xF001 + edges.index(edge)
        form = self._window.native

        def begin():
            user32 = ctypes.windll.user32
            if user32.GetAsyncKeyState(1) & 0x8000:
                user32.ReleaseCapture()
                user32.SendMessageW(ctypes.c_void_p(form.Handle.ToInt64()), 0x0112, command, 0)

        form.BeginInvoke(Action(begin))

    def set_fullscreen(self, on):
        # fullscreen map: the window goes fullscreen too (pywebview only has "toggle")
        on = bool(on)
        if self._window and on != self._full:
            self._window.toggle_fullscreen()
            self._full = on
        return dict(ok=True)

    def get_progress(self):
        # polled by the UI while a scan runs (pywebview uses one thread per call)
        return dict(self._prog)

    def cancel_scan(self):
        self._cancel.set()

    def _scan(self, paths, kits=(), retry=False):
        if not self._scan_lock.acquire(blocking=False):
            return dict(ok=False, error='Scansione in corso…')
        self._cancel.clear()
        cancelled = False
        errors = []
        jobs = [(p, False) for p in paths] + [(p, True) for p in kits]
        try:
            for k, (p, is_kit) in enumerate(jobs):
                def step(done, total, name, k=k, p=p, what='kit' if is_kit else 'progetti'):
                    self._prog = dict(active=True, done=done, total=total, name=name, folder=p, fi=k + 1, fn=len(jobs), what=what)
                _check_cancel(self._cancel)
                step(0, 0, '')
                try:
                    if is_kit:
                        self._store.scan_kits(p, step, self._cancel)
                    else:
                        self._store.scan(p, step, retry, self._cancel)
                except ScanCancelled:
                    raise
                except Exception as e:
                    errors.append(str(e))
        except ScanCancelled:
            cancelled = True
        finally:
            self._prog = dict(active=False)
            self._scan_lock.release()
        return dict(ok=not errors, cancelled=cancelled, error=' | '.join(errors), state=self._store.public())

    def get_state(self):
        s = self._store.public()
        s['coverbase'] = AudioServer.get().cover_base()
        return s

    def choose_folder(self):
        import webview
        kind = getattr(getattr(webview, 'FileDialog', None), 'FOLDER', None) or webview.FOLDER_DIALOG
        res = self._window.create_file_dialog(kind)
        return res[0] if res else None

    def choose_audio(self, path):
        """File dialog to pick the audio to play for a project (its export), starting in the project folder.
        Only returns the chosen path: the UI saves it with set_meta."""
        import webview
        if not self._known(path):
            return None
        kind = getattr(getattr(webview, 'FileDialog', None), 'OPEN', None) or webview.OPEN_DIALOG
        start = os.path.dirname(os.path.normpath(str(path)))
        types = ('Audio (*' + ';*'.join(PLAYABLE) + ')',)
        res = self._window.create_file_dialog(kind, directory=start if os.path.isdir(start) else '', file_types=types)
        return res[0] if res else None

    def choose_image(self, path):
        """File dialog to pick a cover image for a project, starting in the project folder. The image is copied into
        covers\\ in the data folder (the original is only read), so the cover stays if the original is moved."""
        import webview
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        kind = getattr(getattr(webview, 'FileDialog', None), 'OPEN', None) or webview.OPEN_DIALOG
        start = os.path.dirname(os.path.normpath(str(path)))
        types = ('PNG JPG WEBP GIF BMP (*' + ';*'.join(IMAGES) + ')',)  # no words: the dialog label stays the same in every language
        res = self._window.create_file_dialog(kind, directory=start if os.path.isdir(start) else '', file_types=types)
        if not res:
            return dict(ok=True, meta=self._store.meta)
        return self._set_cover(path, res[0])

    @staticmethod
    def _copy_image(key, src):
        """Copies a picked image into covers\\ (the original is only read). Returns dict(ok, name) or dict(ok=False, error)."""
        src = os.path.normpath(str(src))
        if not src.lower().endswith(IMAGES) or not os.path.isfile(src):
            return dict(ok=False, error='File non trovato: ' + src)
        if os.path.getsize(src) > COVER_MAX:
            return dict(ok=False, error='Immagine troppo grande (massimo 20 MB)')
        ext = os.path.splitext(src)[1].lower().replace('.jpeg', '.jpg')
        n, stamp = int(time.time() * 1000), ''
        while n:
            n, r = divmod(n, 36); stamp = '0123456789abcdefghijklmnopqrstuvwxyz'[r] + stamp
        name = hashlib.sha1(key.encode('utf-8')).hexdigest()[:16] + '-' + stamp + ext
        d = covers_dir(); tmp = os.path.join(d, name + '.tmp')
        try:
            shutil.copyfile(src, tmp)  # reads the original, writes only in the data folder
            os.replace(tmp, os.path.join(d, name))
        except OSError as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return dict(ok=False, error='Operazione non riuscita: %s' % e)
        return dict(ok=True, name=name)

    def _set_cover(self, path, src):
        key = os.path.normcase(str(path))
        r = self._copy_image(key, src)
        if not r['ok']:
            return r
        name = r['name']
        with self._store.lock:
            m = dict(self._store.meta.get(key) or {}); old = m.get('cover'); m['cover'] = name
            self._store.meta[key] = m
            self._store.save_meta()
        self._drop_cover(old)
        return dict(ok=True, meta=self._store.meta)

    def remove_image(self, path):
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        key = os.path.normcase(str(path))
        with self._store.lock:
            m = dict(self._store.meta.get(key) or {}); old = m.pop('cover', None)
            if m:
                self._store.meta[key] = m
            else:
                self._store.meta.pop(key, None)
            self._store.save_meta()
        self._drop_cover(old)
        return dict(ok=True, meta=self._store.meta)

    @staticmethod
    def _drop_cover(name):
        # the app's own copy in covers\ (never the original image)
        if name and COVER_RE.match(name):
            try:
                os.remove(os.path.join(covers_dir(), name))
            except OSError:
                pass

    def scan_path(self, path):
        return self._scan([path])

    def rescan_all(self):
        return self._scan(list(self._store.state['paths']), list(self._store.state['kitpaths']))

    def retry_unread(self):
        roots = {os.path.normcase(p.get('root', '')) for p in self._store.state['projects'] if p.get('error')}
        return self._scan([p for p in self._store.state['paths'] if os.path.normcase(p) in roots], retry=True)

    def add_kit_path(self, path):
        return self._scan([], [path])

    def remove_kit_path(self, path):
        st = self._store.state; key = os.path.normcase(path)
        with self._store.lock:
            st['kitpaths'] = [x for x in st['kitpaths'] if os.path.normcase(x) != key]
            st['kitlib'] = {k: v for k, v in st['kitlib'].items() if os.path.normcase(k) != key}
            st['kitmode'] = {k: v for k, v in st['kitmode'].items() if os.path.normcase(k) != key}
            self._store.save()
        return dict(ok=True, state=self._store.public())

    def set_kit_mode(self, path, mode):
        # how to read a kit folder: 'one' = a single kit, 'split' = each subfolder is a kit, '' = the app decides
        st = self._store.state
        with self._store.lock:
            if mode in ('one', 'split'):
                st['kitmode'][path] = mode
            else:
                st['kitmode'].pop(path, None)
            self._store.save()
        return dict(ok=True, state=self._store.public())

    def show_kit(self, path):
        # opens in Explorer a folder inside the user's kit folders. A kit folder can be a whole drive: its root comes as "F:"
        path = str(path)
        path = os.path.normpath(path + os.sep if re.match(r'^[A-Za-z]:$', path) else path); key = os.path.normcase(path)
        if not any(key == os.path.normcase(k) or _inside(path, k) for k in self._store.state['kitpaths']):
            return dict(ok=False, error='Cartella non presente tra le cartelle dei kit')
        if not os.path.isdir(path):
            return dict(ok=False, error='Cartella non trovata: ' + path)
        os.startfile(path)
        return dict(ok=True)

    def remove_path(self, path):
        st = self._store.state; key = os.path.normcase(path)
        with self._store.lock:
            st['paths'] = [x for x in st['paths'] if os.path.normcase(x) != key]
            st.get('inaccessible', {}).pop(path, None)
            st['scanned'].pop(path, None)
            self._store.reroot()  # drops its projects, unless another chosen folder contains them
            self._store.save()
        return dict(ok=True, state=self._store.public())

    def set_containers(self, names):
        with self._store.lock:
            self._store.state['containers'] = sorted({str(n).lower() for n in names})
            self._store.save()
        return dict(ok=True, state=self._store.public())

    def set_pins(self, names):
        # sample folders pinned to the top (in pinning order)
        out = []
        for n in names:
            n = str(n).lower()
            if n not in out:
                out.append(n)
        with self._store.lock:
            self._store.state['pins'] = out
            self._store.save()
        return dict(ok=True)

    def set_prefs(self, prefs):
        if isinstance(prefs, dict):
            with self._store.lock:
                self._store.state['prefs'] = dict(prefs)
                self._store.save_prefs()
        return dict(ok=True)

    def set_meta(self, path, meta):
        """Favourite, tags, note and name given in the app to a project. Only in meta.json: the .flp is never touched."""
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        key = os.path.normcase(str(path)); m = {}
        if isinstance(meta, dict):
            if meta.get('star'):
                m['star'] = True
            tags = [str(t).strip()[:40] for t in (meta.get('tags') or []) if str(t).strip()]
            if tags:
                m['tags'] = list(dict.fromkeys(tags))[:12]
            for k, n in (('note', 4000), ('name', 120)):
                v = str(meta.get(k) or '').strip()[:n]
                if v:
                    m[k] = v
            # audio chosen by the user for the play button: an existing audio file, played read-only
            au = os.path.normpath(str(meta.get('audio') or '')) if meta.get('audio') else ''
            if au and au.lower().endswith(PLAYABLE) and os.path.isfile(au):
                m['audio'] = au
        with self._store.lock:
            # the cover changes only through choose_image / remove_image: any other save keeps it as it is
            cv = (self._store.meta.get(key) or {}).get('cover')
            if cv:
                m['cover'] = cv
            if m:
                self._store.meta[key] = m
            else:
                self._store.meta.pop(key, None)
            self._store.save_meta()
        return dict(ok=True, meta=self._store.meta)

    def get_reviver(self, path):
        """What the Reviver page needs for one project and the library sends only on request: its channels and VSTs, its diary
        and the state of the Reviver folder. ch is None for a project read before channels were read (it will have them after
        the next scan)."""
        key = os.path.normcase(str(path))
        with self._store.lock:
            row = next((p for p in self._store.state['projects'] if os.path.normcase(p['path']) == key), None)
            if row is None:
                return dict(ok=False, error='Progetto non presente nella libreria')
            return dict(ok=True, ch=row.get('ch'), vp=row.get('vp') or {}, diary=self._store.diary.get(key) or {}, folder=reviver_state())

    def save_diary(self, path, data):
        """Notes, names and states given in Reviver to a project. Only in diario.json: the .flp is never touched."""
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        key = os.path.normcase(str(path)); clean = _clean_diary(data)
        with self._store.lock:
            if clean:
                self._store.diary[key] = clean
            else:
                self._store.diary.pop(key, None)
            self._store.save_diary()
        return dict(ok=True)

    # Reviver: what the app writes outside the project is only in its own folder, plus one value in FL's list of folders.
    # Each answer carries the state of the library and the Reviver data of the project, read again
    def _rv_row(self, path):
        if str(path).lower().endswith('.als'):
            return None
        key = os.path.normcase(str(path))
        return next((p for p in self._store.state['projects'] if os.path.normcase(p['path']) == key), None)

    def _rv_after(self, row, names=(), **extra):
        """names: the sounds just copied, which other projects may be looking for too."""
        new = rescan_project(row)
        with self._store.lock:
            st = self._store.state['projects']
            for i, p in enumerate(st):
                if p is row or os.path.normcase(p['path']) == os.path.normcase(row['path']):
                    st[i] = new
                    break
            if names:
                recheck_by_name(st, {n.lower() for n in names})
            self._store.save()
        return dict(ok=True, state=self._store.public(), rv=self.get_reviver(row['path']), **extra)

    def _rv_mark(self, path, name, dest, own=None):
        key = os.path.normcase(str(path)); k = name.lower()
        with self._store.lock:
            d = self._store.diary.setdefault(key, {})
            d.setdefault('copied', {})[k] = dest
            if own:
                d.setdefault('own', {})[k] = own
            else:
                (d.get('own') or {}).pop(k, None)
            self._store.save_diary()

    def _rv_relinked(self, path):
        """The folder was linked or unlinked: FL now finds its sounds, or no longer does, in every project."""
        _flidx['t'] = 0
        out = dict(ok=True, folder=reviver_state())
        names = {f.lower() for _, _, fn in os.walk(out['folder']['dir']) for f in fn}
        if names:
            with self._store.lock:
                recheck_by_name(self._store.state['projects'], names)
                self._store.save()
            out.update(state=self._store.public(), rv=self.get_reviver(path))
        return out

    def link_reviver(self, path):
        """Tells FL about the Reviver folder. Only if FL is closed; the app doesn't close it. path: the project open in the page."""
        if fl_running():
            return dict(ok=False, running=True, folder=reviver_state())
        try:
            link_folder(reviver_dir())
        except OSError as e:
            return dict(ok=False, error=str(e), folder=reviver_state())
        return self._rv_relinked(path)

    def unlink_reviver(self, path):
        if fl_running():
            return dict(ok=False, running=True, folder=reviver_state())
        try:
            unlink_folder(reviver_dir())
        except OSError as e:
            return dict(ok=False, error=str(e), folder=reviver_state())
        return self._rv_relinked(path)

    def open_reviver_dir(self):
        os.startfile(reviver_dir())
        return dict(ok=True)

    def choose_sources(self, kind):
        """File dialog for what the mouse could drop: a folder, or a zip or audio file."""
        import webview
        if kind == 'folder':
            res = self._window.create_file_dialog(getattr(getattr(webview, 'FileDialog', None), 'FOLDER', None) or webview.FOLDER_DIALOG)
        else:
            types = ('ZIP WAV MP3 (*.zip;*' + ';*'.join(AUDIO) + ')',)  # no words: the dialog label stays the same in every language
            res = self._window.create_file_dialog(getattr(getattr(webview, 'FileDialog', None), 'OPEN', None) or webview.OPEN_DIALOG, allow_multiple=True, file_types=types)
        return list(res or [])

    def reviver_add(self, path, sources):
        """What was dropped for a project: copies into the Reviver folder the files it misses, and reports the rest."""
        row = self._rv_row(path)
        if row is None:
            return dict(ok=False, error='Progetto non presente nella libreria')
        if not reviver_state()['linked']:
            return dict(ok=False, needlink=True)
        entries, skipped = [], []
        for src in list(sources or [])[:50]:
            try:
                entries += _source_files(src)
            except (ValueError, OSError, zipfile.BadZipFile) as e:
                log.info('dropped file not read: %s (%s)', src, e)
                skipped.append(os.path.basename(str(src)))
        self._rv_sources = entries
        self._rv_ok = {os.path.normcase(os.path.normpath(e['src'])) for e in entries if not e.get('member')}
        take, unsure, near = match_sources([s['p'] for s in row['samples'] if not s.get('e')], entries)
        copied, failed = [], []
        for s, i in take:
            name = _base(s)
            try:
                dest = copy_source(entries[i], name)
            except (OSError, zipfile.BadZipFile) as e:
                log.warning('not copied: %s (%s)', entries[i]['rel'], e)
                failed.append(name); continue
            self._rv_mark(path, name, dest); copied.append(dict(name=name, to=dest))
        log.info('Reviver: %d audio files looked at, %d copied, %d not copied, %d to choose', len(entries), len(copied), len(failed), len(unsure) + len(near))
        option = lambda i: dict(i=i, name=entries[i]['name'], rel=entries[i]['rel'], size=entries[i]['size'], path=None if entries[i].get('member') else entries[i]['src'])
        used = {i for _, i in take}
        others = [i for i in range(len(entries)) if i not in used]
        return self._rv_after(row, names=[c['name'] for c in copied], report=dict(sources=len(sources or []), found=len(entries), copied=copied, failed=failed, skipped=skipped,
                                               unsure=[dict(name=_base(s), options=[option(i) for i in o]) for s, o in unsure],
                                               near=[dict(name=_base(s), options=[option(i) for i in o]) for s, o in near],
                                               others=[option(i) for i in others[:OTHERS_MAX]], nothers=len(others)))

    def reviver_pick(self, path, sample, i):
        """The file the user chose for a missing sample, among those dropped."""
        row = self._rv_row(path)
        if row is None or not 0 <= int(i) < len(self._rv_sources):
            return dict(ok=False, error='Operazione non riuscita')
        name = _base(str(sample)); e = self._rv_sources[int(i)]
        try:
            dest = copy_source(e, name)
        except (OSError, ValueError, zipfile.BadZipFile) as x:
            return dict(ok=False, error='File non copiato: %s' % x)
        self._rv_mark(path, name, dest, own=None if e['name'].lower() == name.lower() else e['name'])
        return self._rv_after(row, names=[name], report=dict(picked=name, to=dest))

    def reviver_own(self, path, sample):
        """A sound of the user's in place of a missing one: a copy with the name FL looks for; the original stays where it is."""
        import webview
        row = self._rv_row(path)
        if row is None:
            return dict(ok=False, error='Progetto non presente nella libreria')
        if not reviver_state()['linked']:
            return dict(ok=False, needlink=True)
        types = ('Audio (*' + ';*'.join(AUDIO) + ')',)
        res = self._window.create_file_dialog(getattr(getattr(webview, 'FileDialog', None), 'OPEN', None) or webview.OPEN_DIALOG, file_types=types)
        if not res:
            return dict(ok=True, cancelled=True)
        src = os.path.normpath(res[0]); name = _base(str(sample))
        try:
            dest = copy_source(dict(name=name, rel=name, src=src, size=os.path.getsize(src), top=OWN_SOUNDS), name)
        except (OSError, ValueError) as x:
            return dict(ok=False, error='File non copiato: %s' % x)
        self._rv_mark(path, name, dest, own=os.path.basename(src))
        return self._rv_after(row, names=[name], report=dict(own=os.path.basename(src), name=name, to=dest))

    def recheck_project(self, path):
        """Called when the user comes back to the app: if the project was saved in the meantime, it is read again."""
        row = self._rv_row(path)
        if row is None:
            return dict(ok=False, error='Progetto non presente nella libreria')
        try:
            st = os.stat(row['path'])
        except OSError:
            return dict(ok=True, changed=False)
        if st.st_size == row.get('sz') and st.st_mtime == row.get('mt'):
            return dict(ok=True, changed=False)
        return self._rv_after(row, changed=True)

    def start_drag(self, path=None, i=None):
        """Starts dragging a file towards FL, like from Explorer, while the mouse button is down in the page. A file inside a zip
        is first extracted into the Reviver folder, so FL gets a real file that stays there."""
        import ctypes
        if i is not None:
            if not 0 <= int(i) < len(self._rv_sources):
                return dict(ok=False, error='Operazione non riuscita')
            e = self._rv_sources[int(i)]
            try:
                path = copy_source(e, e['name']) if e.get('member') else e['src']
            except (OSError, ValueError, zipfile.BadZipFile) as x:
                return dict(ok=False, error='File non copiato: %s' % x)
        path = os.path.normpath(str(path))
        if not path.lower().endswith(AUDIO) or not os.path.isfile(path) or not self._file_ok(path):
            return dict(ok=False, error='File non trovato: ' + path)
        from System import Action, Array, String
        from System.Windows.Forms import DataObject, DataFormats, DragDropEffects
        form = self._window.native

        def go():
            try:
                ctypes.windll.user32.ReleaseCapture()  # the page holds the mouse: without this the drag doesn't start
                form.DoDragDrop(DataObject(DataFormats.FileDrop, Array[String]([path])), DragDropEffects.Copy)
            except Exception as x:
                log.warning('drag not started: %s', x)
        form.BeginInvoke(Action(go))
        return dict(ok=True)

    def _watch_drops(self):
        """Files dropped on the window: only Python can know their full paths, and the page gets them from here."""
        from webview.dom import DOMEventHandler

        def dropped(e):
            files = (e.get('dataTransfer') or {}).get('files') or []
            paths = [f['pywebviewFullPath'] for f in files if f.get('pywebviewFullPath')]
            log.info('dropped on the window: %d items, %d with a path', len(files), len(paths))
            self._window.evaluate_js('window.rvDropped && rvDropped(%s, %d)' % (json.dumps(paths), len(files)))
        try:
            self._window.dom.document.events.drop += DOMEventHandler(dropped, True, False)
        except Exception as x:
            log.warning('file drop not available: %s', x)

    def add_play(self, path):
        """One listen of a project's audio in the app (the UI calls it after 30 s). Only in ascolti.json."""
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        key = os.path.normcase(str(path))
        with self._store.lock:
            e = self._store.plays.get(key)
            n = e.get('n') if isinstance(e, dict) and isinstance(e.get('n'), int) else 0
            self._store.plays[key] = dict(n=n + 1, t=_utc_now())
            self._store.save_plays()
        return dict(ok=True, plays=self._store.plays)

    def clear_plays(self):
        with self._store.lock:
            self._store.plays = {}
            self._store.save_plays()
        return dict(ok=True, plays={})

    def _albums_out(self):
        return dict(ok=True, albums=dict({k: self._store.albums.get(k) or [] for k in ALBUM_KINDS}, dur=self._store.durations()))

    def save_albums(self, data):
        """Albums and playlists (names, descriptions, release dates, the projects in them and their order).
        Only in album.json: no project or audio file is touched. The image copy of a deleted album is deleted."""
        if not isinstance(data, dict):
            return dict(ok=False, error='Operazione non riuscita')
        with self._store.lock:
            old = self._store.albums
            new = _clean_albums(data, old)
            gone = _album_covers(old) - _album_covers(new)
            self._store.albums = new
            self._store.save_albums()
        for name in gone:
            self._drop_cover(name)
        return self._albums_out()

    def _album(self, kind, aid):
        return next((a for a in self._store.albums.get(kind) or [] if a.get('id') == aid), None) if kind in ALBUM_KINDS else None

    def choose_album_image(self, kind, aid):
        """File dialog for the image of an album or playlist; copied into covers\\ like the project covers."""
        import webview
        if not self._album(kind, aid):
            return dict(ok=False, error='Operazione non riuscita')
        dlg = getattr(getattr(webview, 'FileDialog', None), 'OPEN', None) or webview.OPEN_DIALOG
        types = ('PNG JPG WEBP GIF BMP (*' + ';*'.join(IMAGES) + ')',)
        res = self._window.create_file_dialog(dlg, file_types=types)  # no folder: Windows opens the last one used
        if not res:
            return self._albums_out()
        r = self._copy_image('%s:%s' % (kind, aid), res[0])
        if not r['ok']:
            return r
        with self._store.lock:
            a = self._album(kind, aid)
            old = a.get('cover') if a else None
            if a:
                a['cover'] = r['name']
                self._store.save_albums()
        self._drop_cover(old if a else r['name'])  # the album was deleted meanwhile: the new copy goes too
        return self._albums_out()

    def remove_album_image(self, kind, aid):
        with self._store.lock:
            a = self._album(kind, aid)
            old = a.pop('cover', None) if a else None
            if a:
                self._store.save_albums()
        self._drop_cover(old)
        return self._albums_out()

    def set_durations(self, d):
        """Lengths of audio files measured by the UI (in album pages), kept with the file size."""
        if isinstance(d, dict):
            with self._store.lock:
                dur = self._store.albums.setdefault('dur', {})
                for k, v in list(d.items())[:200]:  # the UI sends a few at a time; each check goes through the library
                    k = os.path.normcase(str(k))
                    if isinstance(v, (int, float)) and 0 < v < 86400 and self._file_ok(k):
                        try:
                            dur[k] = [round(float(v), 1), os.path.getsize(k)]
                        except OSError:
                            pass
                while len(dur) > 20000:
                    dur.pop(next(iter(dur)))
                self._store.save_albums()
        return dict(ok=True)

    def log_js(self, msg):
        # UI errors (window.onerror) in the same log.txt
        log.error('UI: %s', str(msg)[:2000])
        return dict(ok=True)

    def open_data_dir(self):
        os.startfile(os.path.dirname(self._store.file))
        return dict(ok=True)

    # Search online: opens the browser with the search filled in, only on the listed sites. The app downloads nothing
    SITES = dict(google='https://www.google.com/search?q=', youtube='https://www.youtube.com/results?search_query=',
                 splice='https://splice.com/sounds/search?q=', freesound='https://freesound.org/search/?q=',
                 looperman='https://www.looperman.com/loops?keys=', ytvideo='https://www.youtube.com/watch?v=')

    def search_online(self, site, text):
        base = self.SITES.get(str(site)); text = str(text).strip()[:200]
        if not base or not text or (site == 'ytvideo' and not re.match(r'^[A-Za-z0-9_-]{11}$', text)):
            return dict(ok=False, error='Ricerca non valida')
        webbrowser.open(base + urllib.parse.quote_plus(text))
        return dict(ok=True)

    # Open in FL Studio / Show in folder: only projects in the library, and the app doesn't touch the files
    def _known(self, path):
        key = os.path.normcase(str(path))
        return any(os.path.normcase(p['path']) == key for p in self._store.state['projects'])

    def _real(self, p, s, fl=None):
        """Path on disk of a found sample (also with %FLStudioUserData% or found again in the project folder)."""
        if s.get('r'):
            return s['r']
        if not s['p'].startswith('%'):
            return s['p']
        for c in resolve(s['p'], p['dir'], fl or _fl_dirs()):
            if os.path.isfile(c):
                return c
        return None

    def _file_ok(self, path):
        """An audio file known to the library: a found sample of a project or one of its probable exports.
        Only these can be shown in Explorer or played."""
        key = os.path.normcase(os.path.normpath(str(path))); name = os.path.basename(key).lower(); fl = None
        if key in self._rv_ok or key.startswith(os.path.join(os.path.normcase(os.path.join(data_dir(), REVIVER)), '')):
            return True
        if any(os.path.normcase(m.get('audio') or '') == key for m in self._store.meta.values()):
            return True
        for p in self._store.state['projects']:
            for e in p.get('exports', ()):
                if e[0].lower() == name and os.path.normcase(os.path.join(p['dir'], e[0])) == key:
                    return True
            for e in p.get('exo', ()):
                if os.path.normcase(e[0]) == key:
                    return True
            for s in p.get('samples', ()):
                if s.get('e') and _base(s.get('r') or s['p']).lower() == name:
                    if s['p'].startswith('%') and not s.get('r'):
                        fl = fl or _fl_dirs()
                    r = self._real(p, s, fl)
                    if r and os.path.normcase(os.path.normpath(r)) == key:
                        return True
        return False

    def sample_paths(self, path):
        """Real paths of a project's found samples, in the same order as 'samples' (None if missing)."""
        key = os.path.normcase(str(path)); fl = _fl_dirs()
        for p in self._store.state['projects']:
            if os.path.normcase(p['path']) == key:
                return dict(ok=True, paths=[self._real(p, s, fl) if s.get('e') else None for s in p.get('samples', ())])
        return dict(ok=False, error='Progetto non presente nella libreria')

    def _is_backup(self, path):
        key = os.path.normcase(path)
        return any(os.path.normcase(b[0]) == key for p in self._store.state['projects'] for b in p.get('bk', ()))

    def show_file(self, path):
        path = os.path.normpath(str(path))
        if not (self._file_ok(path) or self._is_backup(path)) or not os.path.isfile(_lp(path)):
            return dict(ok=False, error='File non trovato: ' + path)
        subprocess.Popen(['explorer', '/select,' + path])
        return dict(ok=True)

    def audio_url(self, path):
        """Local URL (127.0.0.1, this PC only) from which the UI can play an export or a sample."""
        path = os.path.normpath(str(path))
        if not self._file_ok(path) or not os.path.isfile(_lp(path)):
            return dict(ok=False, error='File non trovato: ' + path)
        server = AudioServer.get()
        if self._window is not None:
            server.set_ui_url(self._window.get_current_url())
        return dict(ok=True, url=server.url(path))

    def show_in_folder(self, path):
        row = next((p for p in self._store.state['projects'] if os.path.normcase(p['path']) == os.path.normcase(str(path))), None)
        if not row:
            return dict(ok=False, error='Progetto non presente nella libreria')
        folder = os.path.normpath(row['dir'])
        if not os.path.isdir(_lp(folder)):
            return dict(ok=False, error='Cartella non trovata: ' + folder)
        os.startfile(_lp(folder))
        return dict(ok=True)

    def open_project(self, path):
        if not self._known(path):
            return dict(ok=False, error='Progetto non presente nella libreria')
        path = os.path.normpath(path)
        if not os.path.isfile(path):
            return dict(ok=False, error='File non trovato: ' + path)
        try:
            os.startfile(path)  # the program Windows uses for .flp files (FL Studio)
        except OSError:
            if path.lower().endswith('.als'):
                return dict(ok=False, error='Associa i file .als ad Ableton Live in Windows')
            exe = _fl_exe()
            if not exe:
                return dict(ok=False, error='Windows non sa con cosa aprire i .flp e FL Studio non è nella cartella solita')
            subprocess.Popen([exe, path])
        return dict(ok=True)


# ------------------------------------------------------------------ playback
class AudioServer:
    """Minimal HTTP server on 127.0.0.1 (port chosen by Windows), only for the UI's <audio> element.
    Serves READ-ONLY the files checked by Api.audio_url (exports and samples of the library), each at a
    random URL; supports Range, so playback can seek. Not reachable from other PCs."""
    _one = None
    _start = threading.Lock()  # started at launch in a thread, and asked for by get_state: only one server

    @classmethod
    def get(cls):
        with cls._start:
            if cls._one is None:
                cls._one = cls()
        return cls._one

    def __init__(self):
        self.files = {}
        self.ui_origin = None
        owner = self
        self.lock = threading.Lock()  # pywebview runs each call in its own thread: two quick ▶ clicks call url() together
        files = self.files

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                host = self.headers.get('Host', '').lower()
                expected = '127.0.0.1:%d' % self.server.server_port
                origin = self.headers.get('Origin')
                if host != expected or (origin is not None and origin not in ('null', owner.ui_origin)):
                    self.send_error(403); return
                name = self.path.lstrip('/').split('?')[0]
                # covers: only the copies in covers\ of the data folder, by their exact name
                path = os.path.join(covers_dir(), name[3:]) if name.startswith('cv/') and COVER_RE.match(name[3:]) else files.get(name)
                if not path or not os.path.isfile(_lp(path)):
                    self.send_error(404); return
                size = os.path.getsize(_lp(path)); a, b = 0, size - 1
                m = re.match(r'bytes=(\d*)-(\d*)$', self.headers.get('Range', ''))
                if m and (m.group(1) or m.group(2)):
                    if m.group(1):
                        a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else size - 1
                    else:
                        a = max(0, size - int(m.group(2)))
                    b = min(b, size - 1)
                    if a > b:
                        self.send_error(416); return
                    self.send_response(206); self.send_header('Content-Range', 'bytes %d-%d/%d' % (a, b, size))
                else:
                    self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
                self.send_header('Accept-Ranges', 'bytes'); self.send_header('Content-Length', str(b - a + 1))
                if origin is not None:
                    self.send_header('Access-Control-Allow-Origin', origin)
                    self.send_header('Vary', 'Origin')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                try:
                    with open(_lp(path), 'rb') as f:  # READ ONLY
                        f.seek(a); left = b - a + 1
                        while left > 0:
                            chunk = f.read(min(262144, left))
                            if not chunk:
                                break
                            self.wfile.write(chunk); left -= len(chunk)
                except (ConnectionError, OSError):
                    pass

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

            def server_bind(self):
                # HTTPServer would ask Windows for the PC name of 127.0.0.1 (getfqdn): it can block for seconds
                socketserver.TCPServer.server_bind(self)
                self.server_name, self.server_port = '127.0.0.1', self.server_address[1]

        self.srv = S(('127.0.0.1', 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def set_ui_url(self, url):
        parsed = urllib.parse.urlsplit(url or '')
        if parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and parsed.port:
            self.ui_origin = '%s://%s' % (parsed.scheme, parsed.netloc)

    def url(self, path):
        with self.lock:
            for k, v in self.files.items():
                if v == path:
                    break
            else:
                k = secrets.token_urlsafe(16) + os.path.splitext(path)[1].lower()
                self.files[k] = path
        return 'http://127.0.0.1:%d/%s' % (self.srv.server_address[1], k)

    def cover_base(self):
        return 'http://127.0.0.1:%d/cv/' % self.srv.server_address[1]


# ------------------------------------------------------------------ error log
def setup_log():
    """%APPDATA%\\ProjectSeeker\\log.txt: the exe has no console, this is the only way to understand users' problems."""
    try:
        h = logging.handlers.RotatingFileHandler(os.path.join(data_dir(), 'log.txt'), maxBytes=512 * 1024, backupCount=1, encoding='utf-8', errors='backslashreplace')
    except OSError:
        return
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log.addHandler(h); log.setLevel(logging.INFO)
    # pywebview logs exceptions of UI calls to its own logger: they end up here too
    pw = logging.getLogger('pywebview'); pw.addHandler(h)
    log.info('Project Seeker %s, Python %s, %s', VERSION, sys.version.split()[0], sys.platform)
    sys.excepthook = lambda t, v, tb: log.error('unhandled error', exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.error('unhandled error (thread)', exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


# ------------------------------------------------------------------ WebView2
WV2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
WV2_URL = 'https://developer.microsoft.com/microsoft-edge/webview2/'


def has_webview2():
    """Without WebView2 pywebview cannot use Edge and the UI doesn't work. Registry keys as in Microsoft's documentation."""
    try:
        import winreg
    except ImportError:
        return True
    for hive, sub in ((winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\WOW6432Node\\Microsoft\\EdgeUpdate\\Clients\\' + WV2),
                      (winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\' + WV2),
                      (winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\EdgeUpdate\\Clients\\' + WV2)):
        try:
            with winreg.OpenKey(hive, sub) as k:
                v = winreg.QueryValueEx(k, 'pv')[0]
                if v and v != '0.0.0.0':
                    return True
        except OSError:
            pass
    return False


def need_webview2():
    """Windows message box offering to open the download page. True if the app must stop."""
    if has_webview2():
        return False
    log.error('WebView2 not installed')
    text = {
        'it': 'Project Seeker ha bisogno di Microsoft Edge WebView2, che su questo PC non c\'è.\n\n'
              'È gratuito e lo usano molte app di Windows. Aprire la pagina di download?',
        'fr': 'Project Seeker a besoin de Microsoft Edge WebView2, qui n\'est pas installé sur ce PC.\n\n'
              'Il est gratuit et utilisé par de nombreuses applications Windows. Ouvrir la page de téléchargement ?',
        'de': 'Project Seeker benötigt Microsoft Edge WebView2, das auf diesem PC nicht installiert ist.\n\n'
              'Es ist kostenlos und wird von vielen Windows-Apps verwendet. Download-Seite öffnen?',
    }.get(sys_lang(), 'Project Seeker needs Microsoft Edge WebView2, which is not installed on this PC.\n\n'
                      'It is free and used by many Windows apps. Open the download page?')
    try:
        import ctypes
        if ctypes.windll.user32.MessageBoxW(None, text, 'Project Seeker', 0x04 | 0x30) == 6:  # Yes / No, warning icon
            webbrowser.open(WV2_URL)
    except Exception:
        pass
    return True


def fake_library(n):
    """N made-up projects for the load test, always the same ones: nothing on disk is read, and none of them exists."""
    rnd = random.Random(20000)
    words = 'dark night lead trap drill wave ghost neon velvet ombra città perché notte sogno fuoco nuvole gold silver storm river echo drift pulse ember shadow blue rain'.split()
    gens = ['Serum x64', 'Nexus', 'Sylenth1', 'Vital', 'FLEX', 'Sytrus', '3x Osc', 'Harmor', 'Omnisphere', 'Kontakt 7', 'Massive X', 'Spire', 'Pigments', 'Analog Lab V', 'FPC', 'Sampler']
    effects = ['Pro-Q 3', 'Pro-L 2', 'Fruity Limiter', 'Fruity Parametric EQ 2', 'Soothe2', 'Valhalla Room', 'Ozone 11', 'Saturn 2', 'CLA-76', 'RC-20 Retro Color', 'Gross Beat', 'Maximus', 'Decapitator', 'OTT']
    native = {'FLEX', 'Sytrus', '3x Osc', 'Harmor', 'FPC', 'Sampler', 'Fruity Limiter', 'Fruity Parametric EQ 2', 'Gross Beat', 'Maximus'}
    kinds = ['kick', 'snare', 'clap', 'hat', 'open hat', 'perc', '808', 'vox', 'loop', 'fx', 'crash', 'rim']
    kits = ['Cymatics Oracle', 'Pop Smoke Kit', 'Trap Essentials', 'Drill Essentials', 'Bedroom Kit']
    scales = ['Minor', 'Major', 'Minor Harmonic', 'Dorian', 'Phrygian']
    out = []
    for i in range(n):
        generic = rnd.random() < 0.3
        name = 'Project_%d' % i if generic else ' '.join(rnd.sample(words, rnd.randint(1, 3))) + (' %d' % rnd.randint(1, 40) if rnd.random() < 0.4 else '')
        folder = 'Progetto %d' % (i // 8)
        d = 'C:\\Musica\\Beat finti\\%s' % folder
        year = rnd.randint(2018, 2026)
        created = '%d-%02d-%02d' % (year, rnd.randint(1, 12), rnd.randint(1, 28))
        modified = '%d-%02d-%02d' % (min(2026, year + rnd.randint(0, 2)), rnd.randint(1, 10), rnd.randint(1, 28))
        hours = round(min(40, rnd.lognormvariate(-0.5, 1.4)), 3)
        samples, nmiss = [], rnd.choice((0, 0, 0, 1, 2, 4, 8, 30))
        for k in range(rnd.randint(3, 60)):
            base = '%s %s %d.wav' % (rnd.choice(kits), rnd.choice(kinds), rnd.randint(1, 120))
            if k < nmiss:
                root = rnd.choice(('C:\\Users\\VecchioPC\\Desktop\\', 'Z:\\Sample\\', 'C:\\Sample persi\\'))
                samples.append(dict(p=root + base, e=False, s=0, l=False))
            else:
                samples.append(dict(p='C:\\Sample\\' + base, e=True, s=rnd.randint(50000, 8000000), l=False))
        chosen_g = rnd.sample(gens, rnd.randint(1, 6)); chosen_f = rnd.sample(effects, rnd.randint(0, 8))
        row = dict(path='%s\\%s.flp' % (d, name), root='C:\\Musica\\Beat finti', dir=d, folder=folder, name=name, error='', partial=False,
                   version='%d.%d.%d.%d' % (rnd.choice((20, 21, 21, 24, 25, 25, 26)), rnd.randint(0, 2), rnd.randint(0, 9), rnd.randint(1000, 5999)),
                   bpm=rnd.choice((rnd.randint(60, 200), rnd.randint(130, 160))) + rnd.choice((0, 0, 0, 0.5)), created=created, modified=modified, hours=hours,
                   samples=samples, native=[x for x in chosen_g + chosen_f if x in native], vst=[x for x in chosen_g + chosen_f if x not in native],
                   gen=chosen_g, fx=chosen_f, pat=rnd.randint(0, 80), chn=rnd.randint(1, 60), kb=rnd.randint(30, 4000), pv=PARSER, hc='%032x' % rnd.getrandbits(128),
                   exports=[], backups=0)
        roll = rnd.random()
        if roll < 0.25:
            row['exports'] = [[name + ' master.wav', rnd.randint(10 ** 7, 10 ** 8), rnd.randint(70, 100)]]
        elif roll < 0.3:
            row['exo'] = [['C:\\Musica\\Export finti\\%s.wav' % name, rnd.randint(10 ** 7, 10 ** 8), rnd.randint(55, 90)]]
        if rnd.random() < 0.08:
            row['backups'] = 2
            row['bk'] = [['%s\\Backup\\%s (overwritten on 01.0%d.2026 at 1%dh00).flp' % (d, name, k + 1, k), 90000, '2026-0%d-01 1%d:00' % (k + 1, k)] for k in range(2)]
        if rnd.random() < 0.2:
            row.update(key='%s %s' % (rnd.choice(NOTES), rnd.choice(scales)), kf='fl')
        elif rnd.random() < 0.1:
            row.update(key='%s minor' % rnd.choice('ABCDEFG'), kf='nome')
        if rnd.random() < 0.1:
            row.update(title=name.title(), artist=rnd.choice(('Prod. Finto', 'Nessuno', 'Artista di Prova')))
        if out and rnd.random() < 0.03:  # an identical copy of an earlier project, in another folder
            twin = out[rnd.randrange(len(out))]
            row.update(hc=twin['hc'], name=twin['name'], path='%s\\%s.flp' % (d, twin['name']))
        if rnd.random() < 0.003:
            row.update(error=READ_ERRORS['no_data'], ec='no_data', samples=[], native=[], vst=[], gen=[], fx=[], version='', hc='', bpm=None, hours=None, created='')
        out.append(row)
    return out


class ProvaApi(Api):
    """Load test: a made-up library of N projects, in memory only.
    Writes nothing (not even libreria.json): scans and list changes are disabled."""
    def __init__(self, n):
        super().__init__()
        real = self._store.state
        out = fake_library(n)
        self._fake = dict(paths=sorted({p['root'] for p in out}), scanned={}, containers=[], pins=[], prefs=dict(real.get('prefs', {})),
                          kitpaths=[], kitlib={}, kitmode={}, projects=out, home=os.path.expanduser('~'), datafile=self._store.file, syslang=sys_lang(),
                          meta={}, plays={}, albums=dict({k: [] for k in ALBUM_KINDS}, dur={}), drives=_drives(), flpaths=[], version=VERSION)

    def get_state(self):
        self._fake['coverbase'] = AudioServer.get().cover_base()
        return self._fake

    def assistant_chats(self):
        return []

    def assistant_chat_save(self, chat_id, messages):
        return dict(ok=False, error='Prova: salvataggio disattivato')

    def assistant_chat_delete(self, chat_id):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def choose_image(self, path):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def remove_image(self, path):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def _scan(self, paths, kits=(), retry=False):
        return dict(ok=False, error='Prova da %d progetti: scansione disattivata' % len(self._fake['projects']), state=self._fake)

    def remove_path(self, path):
        return dict(ok=False, error='Prova: elenco cartelle bloccato', state=self._fake)

    def remove_kit_path(self, path):
        return dict(ok=False, error='Prova: elenco cartelle bloccato', state=self._fake)

    def set_kit_mode(self, path, mode):
        return dict(ok=False, error='Prova: modifiche disattivate', state=self._fake)

    def set_containers(self, names):
        return dict(ok=False, error='Prova: modifiche disattivate', state=self._fake)

    # in the load test, pins and preferences last only while the window is open
    def set_pins(self, names):
        self._fake['pins'] = [str(n).lower() for n in names]
        return dict(ok=True)

    def set_prefs(self, prefs):
        if isinstance(prefs, dict):
            self._fake['prefs'] = dict(prefs)
        return dict(ok=True)

    def set_meta(self, path, meta):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def get_reviver(self, path):
        return dict(ok=True, ch=None, vp={}, diary={}, folder=reviver_state())

    def save_diary(self, path, data):
        return dict(ok=True)  # nothing is written in the load test

    def _no_files(self, *a, **k):
        return dict(ok=False, error='Prova: modifiche disattivate')

    reviver_add = reviver_pick = reviver_own = link_reviver = unlink_reviver = _no_files

    def recheck_project(self, path):
        return dict(ok=True, changed=False)

    # listens last only while the window is open
    def add_play(self, path):
        key = os.path.normcase(str(path)); e = self._fake['plays'].get(key) or {}
        self._fake['plays'][key] = dict(n=int(e.get('n') or 0) + 1, t=_utc_now())
        return dict(ok=True, plays=self._fake['plays'])

    def clear_plays(self):
        self._fake['plays'] = {}
        return dict(ok=True, plays={})

    def save_albums(self, data):
        if not isinstance(data, dict):
            return dict(ok=False, error='Operazione non riuscita')
        self._fake['albums'] = dict(_clean_albums(data, self._fake['albums']), dur={})
        return dict(ok=True, albums=self._fake['albums'])

    def choose_album_image(self, kind, aid):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def remove_album_image(self, kind, aid):
        return dict(ok=False, error='Prova: modifiche disattivate')

    def set_durations(self, d):
        return dict(ok=True)

    # the fake copies point to the real project they were made from (also their exports: "<dir>#3\file.wav")
    def audio_url(self, path):
        return super().audio_url(re.sub(r'#\d+(?=[\\/])', '', str(path)))

    def show_file(self, path):
        return super().show_file(re.sub(r'#\d+(?=[\\/])', '', str(path)))

    def sample_paths(self, path):
        return super().sample_paths(re.sub(r'#\d+$', '', str(path)))

    def show_in_folder(self, path):
        return super().show_in_folder(re.sub(r'#\d+$', '', path))

    def open_project(self, path):
        return super().open_project(re.sub(r'#\d+$', '', path))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--dump':
        out = dict(paths=[sys.argv[2]], scanned={}, containers=[], projects=scan_root(sys.argv[2]), home=os.path.expanduser('~'))
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        json.dump(out, sys.stdout, ensure_ascii=False)
        return
    setup_log()
    if need_webview2():
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--load-test':
        import webview
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        api = ProvaApi(int(sys.argv[2]))
        api._window = webview.create_window('Project Seeker - load test, %s projects' % sys.argv[2], os.path.join(base, 'ui', 'index.html'),
                                           js_api=api, width=1360, height=900, min_size=(900, 600), easy_drag=False, background_color='#0B0B0C')
        api._window.events.before_show += api._install_window_frame
        webview.start()
        return
    import webview
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    threading.Thread(target=AudioServer.get, daemon=True).start()  # ready before the first ▶
    api = Api()
    log.info('start: %s (exe: %s), pywebview %s', base, getattr(sys, 'frozen', False), getattr(webview, '__version__', '?'))
    api._window = webview.create_window('Project Seeker', os.path.join(base, 'ui', 'index.html'), js_api=api,
                                       width=1360, height=900, min_size=(900, 600), easy_drag=False, background_color='#0B0B0C')
    api._window.events.before_show += api._install_window_frame
    api._window.events.loaded += api._watch_drops
    webview.start()
    log.info('window closed')


def run():
    # any startup error (also in the exe, which has no console) goes to log.txt and to a Windows message box
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        import traceback
        tb = traceback.format_exc()
        try:
            setup_log() if not log.handlers else None
            log.error('start failed\n%s', tb)
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'Project Seeker non si è avviato:\n\n%s: %s\n\nDettagli in %%APPDATA%%\\ProjectSeeker\\log.txt' % (type(e).__name__, e), 'Project Seeker', 0x10)
        except Exception:
            pass
        raise


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()  # in the exe a reader starts as the exe itself: this is what sends it to its work
    run()
