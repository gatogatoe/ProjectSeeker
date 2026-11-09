# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""Writes the fake .flp files of the difficult cases to test/: damaged, empty, very old or very new files, odd data and odd names.
Each one must either be read as far as possible or be reported as not read, and it must never stop a scan.
    python test/make_edge_flp.py"""
import os, struct
from make_fake_flp import ev, u16

HEADER = b'FLhd' + struct.pack('<IhhH', 6, 0, 1, 96)


def body(events):
    return HEADER + b'FLdt' + struct.pack('<I', len(events)) + events


def common(version, bpm=140):
    return ev(199, (version + '\0').encode()) + ev(156, struct.pack('<I', int(bpm * 1000))) + ev(237, struct.pack('<dd', 45000.5, 1.5 / 24))


def info_project():
    # the way FL really saves these: 194 title, 207 artist, 243 scale and root, 65 one event per pattern with notes
    e = common('26.1.7.5654') + ev(192, u16('FL Studio 26.1.7.5654.5654')) + ev(194, u16('Night Drive')) + ev(195, u16('a comment')) + ev(206, u16('Trap')) + ev(207, u16('Someone'))
    e += ev(64, struct.pack('<H', 0)) + ev(201, u16('FLEX')) + ev(213, b'\0' * 32)
    e += ev(64, struct.pack('<H', 1)) + ev(201, u16('Fruity Wrapper')) + ev(213, b'\0' * 4 + struct.pack('<IQ', 54, 5) + b'Serum')
    e += ev(64, struct.pack('<H', 2)) + ev(196, u16('Samples\\relative kick.wav'))
    e += ev(65, struct.pack('<H', 1)) + ev(65, struct.pack('<H', 2)) + ev(65, struct.pack('<H', 2)) + ev(65, struct.pack('<H', 5))
    e += ev(99) + ev(201, u16('Fruity Limiter')) + ev(213, b'\0' * 16) + ev(201, u16('Fruity Wrapper')) + ev(213, b'\0' * 4 + struct.pack('<IQ', 54, 5) + b'Pro-Q')
    e += ev(243, struct.pack('<ii', 10, 3))
    return body(e)


def odd_values():
    # a tempo and a time that make no sense, a date Windows can't count: the rest of the project still has to come through
    e = ev(199, b'24.1.0.1\0') + ev(156, struct.pack('<I', 4000000000)) + ev(237, struct.pack('<dd', 1e300, float('nan')))
    e += ev(194, u16('Still Here')) + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Samples\\odd.wav')) + ev(99) + ev(243, struct.pack('<ii', 99, 99))
    return body(e)


def main():
    d = os.path.dirname(os.path.abspath(__file__))
    good = body(common('26.1.0.1') + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Samples\\snare.wav')) + ev(99))
    copy = body(common('24.2.0.1', 128) + ev(194, u16('The Copy')) + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Samples\\copy.wav')) + ev(99))
    files = {
        'edge_empty.flp': b'',
        'edge_only_header.flp': HEADER,
        'edge_not_flp.flp': b'this is a text file renamed to .flp\r\n' * 40,
        'edge_no_data.flp': HEADER + b'FLdt' + struct.pack('<I', 0),
        'edge_bad_header_length.flp': b'FLhd' + struct.pack('<I', 999999) + good[8:],
        'edge_cut_in_half.flp': good[:len(good) - 12],
        'edge_garbage_after_header.flp': HEADER + b'FLdt' + struct.pack('<I', 500) + bytes(range(256)) * 2,
        'edge_very_old_fl9.flp': body(common('9.0.0.1') + ev(64, struct.pack('<H', 0)) + ev(196, 'C:\\Vecchi\\càssa.wav\0'.encode('latin-1')) + ev(99)),
        'edge_very_new_fl99.flp': body(common('99.0.0.1') + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Samples\\new.wav')) + ev(99)),
        'edge_no_version.flp': body(ev(156, struct.pack('<I', 90000)) + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Samples\\x.wav')) + ev(99)),
        'edge_odd_values.flp': odd_values(),
        'edge_info_key_patterns.flp': info_project(),
        # two identical files and a backup of one of them, as FL 26 and older versions name it
        'edge_copy_one.flp': copy,
        'edge_copy_two.flp': copy,
        'edge_copy_one (overwritten on 19.10.2026 at 23h00).flp': good,
        'edge_copy_one (autosaved at 10h54).flp': good,
        'edge_nome strano àè & #1 [x] (2) 日本語 🎵.flp': body(common('25.1.0.1') + ev(64, struct.pack('<H', 0)) + ev(196, u16('C:\\Kits\\strano àè #1 🎵.wav')) + ev(99)),
    }
    for name, b in files.items():
        with open(os.path.join(d, name), 'wb') as f:
            f.write(b)
        print('written', name.encode('ascii', 'replace').decode())


if __name__ == '__main__':
    main()
