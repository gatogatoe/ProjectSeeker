# Copyright (C) 2026 Gato
# SPDX-License-Identifier: GPL-3.0-only
# Licensed under the GNU General Public License v3.0; see LICENSE.
"""Writes a few fake .flp files to test/ (only the events Project Seeker reads), for the reader's tricky cases:
event 0xAC of FL 25 (3 bytes) and FL 26 (variable length), samples inside a native plugin (FPC), and the channel rack
with renamed channels and the saved data of synths.
They don't replace real .flp files: test/ also needs small projects saved by each FL version (20, 21, 24, 25, 26).
    python test/make_fake_flp.py"""
import struct, zlib

def ev(i, d=b''):
    if i < 64: return bytes([i]) + d[:1].ljust(1, b'\0')
    if i < 128: return bytes([i]) + d[:2].ljust(2, b'\0')
    if i < 192: return bytes([i]) + d[:4].ljust(4, b'\0')
    n = len(d); out = bytearray([i])
    while True:
        c = n & 0x7f; n >>= 7
        out.append(c | (0x80 if n else 0))
        if not n: break
    return bytes(out) + d

def u16(s): return (s + '\0').encode('utf-16-le')

def flp(version='25.2.4.4960', bpm=140, created=45000.5, hours=1.5, samples=(), plugins=(), vsts=()):
    e = ev(199, (version + '\0').encode()) + ev(156, struct.pack('<I', int(bpm * 1000))) + ev(237, struct.pack('<dd', created, hours / 24))
    for s in samples: e += ev(64, b'\0') + ev(196, u16(s))
    e += ev(99)  # the channel rack ends here: the plugins below are in the mixer
    for name, data in plugins: e += ev(201, u16(name)) + ev(212, b'\0' * 8) + ev(213, data)
    for v in vsts:
        sub = struct.pack('<IQ', 54, len(v.encode())) + v.encode()
        e += ev(201, u16('Fruity Wrapper')) + ev(212, b'\0' * 8) + ev(213, b'\0' * 4 + sub)
    return b'FLhd' + struct.pack('<IhhH', 6, 0, 1, 96) + b'FLdt' + struct.pack('<I', len(e)) + e


def vst_data(name, where='', state=b''):
    block = lambda cid, b: struct.pack('<IQ', cid, len(b)) + b
    return b'\0' * 4 + block(54, name.encode()) + block(55, where.encode()) + block(53, state)


def serum_state(preset, author=b'', table_a=b'', table_b=b'', noise=b'', inside=False):
    x = bytearray(20704)
    for at, text in ((15368, table_a), (15880, table_b), (16392, noise), (18802, preset), (18848, author)):
        x[at:at + len(text)] = text
    x[18800:18802] = b'\x01\t'
    return b'\xf7\xff\xff\xff\x0d\xfe\xff\xff\xff' + b'\0' * 12 + zlib.compress(bytes(x), 6) + (zlib.compress(bytes(range(256)) * 32) if inside else b'')


def flex_data(pack, preset):
    x = bytearray(2707)
    x[16:16 + len(pack)] = pack
    x[1041:1041 + len(preset)] = preset
    return bytes(x)


def rack_flp():
    def channel(n, kind, name='', inner='', file='', data=None):
        c = ev(64, struct.pack('<H', n)) + ev(21, bytes([kind])) + ev(201, u16(inner)) + ev(203, u16(name))
        if file: c += ev(196, u16(file))
        if data is not None: c += ev(212, b'\0' * 8) + ev(213, data)
        return c
    wrap = 'Fruity Wrapper'
    rack = [
        channel(0, 0, 'Sampler'),                                                  # empty: left out
        channel(1, 0, 'kick 01', file='C:\\Kits\\kick 01.wav'),                    # named like its file: no name kept
        channel(2, 0, 'My Snare', file='C:\\Kits\\snare 03.wav'),                  # renamed
        channel(3, 4, 'vox take', file='C:\\Kits\\vox take.wav'),                  # audio clip
        channel(4, 5, 'Automation'),                                               # left out
        channel(5, 2, 'Nexus', wrap, data=vst_data('Nexus', 'C:\\VST3\\Nexus.vst3', b'NEXUS4.5 Bank\0\0\0' + bytes(range(200)))),
        channel(6, 2, 'Lead Night', wrap, data=vst_data('Nexus', 'C:\\VST3\\Nexus.vst3', b'NEXUS4.5 Bank\0\0\0')),
        channel(7, 2, 'Serum', wrap, data=vst_data('Serum', 'C:\\VST\\Serum_x64.dll', serum_state(b'Night Lead', b'Someone', b'Analog/Basic Shapes.wav', b'\\Digital\\Saw.wav', b'Organics\\AC hum1.wav', inside=True))),
        channel(8, 2, 'Serum #2', wrap, data=vst_data('Serum', 'C:\\VST\\Serum_x64.dll', serum_state(b' - Init - ', noise=b'Custom Noise'))),
        channel(9, 2, 'Serum #3', wrap, data=vst_data('Serum', 'C:\\VST\\Serum_x64.dll', b'not what Serum saves')),
        channel(10, 2, 'Vital', wrap, data=vst_data('Vital', 'C:\\VST3\\Vital.vst3', b'\0\0{"author":"Someone","comments":"","preset_name":"Deep \\"Bass\\"","settings":{}}')),
        channel(11, 2, 'Addictive Keys', wrap, data=vst_data('Addictive Keys', 'C:\\VST\\AK.dll', b'x ExploreFile = "StGrandProducer.Explore" y')),
        channel(12, 2, 'Arcade', wrap, data=vst_data('Arcade', 'C:\\VST\\Arcade.dll', b'<?xml?><info name="Rain &amp; Snow" uuid="1"/><info name="Rain &amp; Snow" uuid="1"/><info name="Still" uuid="2"/>')),
        channel(13, 2, 'Bell Pad', 'FLEX', data=flex_data(b'Essential Winds', b'Bell Pad')),
        channel(14, 2, 'FL Keys', 'FL Keys', data=b'\0' * 5 + b'Grand Piano\x01' + b'\0' * 60),
        channel(15, 2, 'Sub', '3x Osc', data=b'\0' * 16),                          # native plugin, nothing to read
    ]
    # an effect in the mixer: its plugin path counts, but it is not a channel
    e = ev(199, b'26.1.0.1\0') + b''.join(rack) + ev(99) + ev(201, u16(wrap)) + ev(203, u16('Pro-Q')) + ev(213, vst_data('Pro-Q', 'C:\\VST3\\ProQ.vst3'))
    return b'FLhd' + struct.pack('<IhhH', 6, 0, 1, 96) + b'FLdt' + struct.pack('<I', len(e)) + e


def main():
    import os
    d = os.path.dirname(os.path.abspath(__file__))
    base = flp(version='21.2.3.4004', bpm=140, samples=['C:\\Samples\\kick.wav', '%FLStudioUserData%\\Projects\\beat\\vocals.wav'], plugins=[('Sytrus', b'\0' * 32)], vsts=['Serum'])
    # FL 25.2: event 0xAC has 3 bytes instead of 4 (a 0xC0 text event always follows)
    e = struct.pack('<IhhH', 6, 0, 1, 96)
    ev25 = ev(199, b'25.2.4.4960\0') + ev(156, struct.pack('<I', 150000)) + bytes([0xAC]) + b'\x01\x02\x03' + ev(0xC0, u16('Pattern 1')) + ev(64, b'\0') + ev(196, u16('C:\\Samples\\snare.wav'))
    fl25 = b'FLhd' + e + b'FLdt' + struct.pack('<I', len(ev25)) + ev25
    # FL 26 (according to the Meowrium/PyFLP fork): 0xAC with a length byte in front
    ev26 = ev(199, b'26.0.0.1\0') + ev(156, struct.pack('<I', 128000)) + bytes([0xAC, 6]) + b'\x01\x02\x03\x04\x05\x06' + ev(0xC0, u16('Pattern 1')) + ev(64, b'\0') + ev(196, u16('C:\\Samples\\hat.wav'))
    fl26 = b'FLhd' + e + b'FLdt' + struct.pack('<I', len(ev26)) + ev26
    # FPC with a wav inside its data (UTF-16) and one in plain text
    fpc = b'\x10\x00' + u16('C:\\Users\\User\\Desktop\\fpc snare.wav') + b'\x00\x00\x07' + b'D:\\kits\\fpc kick.wav\0'
    plug = flp(version='24.2.1.4526', bpm=95, samples=[], plugins=[('FPC', fpc)])
    for name, b in (('fl21_base.flp', base), ('fl25_event_ac_3_bytes.flp', fl25), ('fl26_event_ac_length.flp', fl26), ('fl24_fpc_with_samples.flp', plug), ('fl26_channels_and_synths.flp', rack_flp())):
        with open(os.path.join(d, name), 'wb') as f:
            f.write(b)
        print('written', name)


if __name__ == '__main__':
    main()
