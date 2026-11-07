#!/usr/bin/env python3
"""unpoke_code.code_pointers: the image words that hold a code address keep the image's value in a case's pokes.

    python3 tests/unpoke/check.py

Cases:
    table     a poke over a jump table (Zombie Revenge FUN_0c0b4f84: 0C203FBC, random words made the original jump to
              0C203FBD and fault): the entries that are function addresses get the image's words back, the data words in
              the same poke stay as drawn
    mirror    a code address written through the 8C mirror counts the same
    outside   a poke outside the image (the cases' own buffers at 0C800000) is left as it is
    middle    an address inside a function (not its start) counts as code too; one past its end does not
    edges     a poke that starts mid-word or covers part of a code word: only whole words inside the poke are restored
    same_fault mark_same_fault: every case of a file gets same_fault, nothing else changes
    drop      drop_faulting: the cases on which the original stops are removed, the others kept as they were
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 'tools', '6-agentic'))
import unpoke_code  # noqa: E402

BASE = 0x0C010000
img = bytearray(0x200)
spans = [(0x0C010000, 0x40), (0x0C010040, 0x20)]           # two functions, 0C010000-0C010060
table = 0x0C010100
for i, w in enumerate((0x0C010000, 0x8C010040, 0x00001234, 0x0C010050, 0x0C010060)):
    struct.pack_into('<I', img, table - BASE + 4 * i, w)
img = bytes(img)
bad = []


def words(h):
    b = bytes.fromhex(h)
    return [struct.unpack_from('<I', b, 4 * i)[0] for i in range(len(b) // 4)]


drawn = struct.pack('<5I', 0x0C203FBD, 0x0C930100, 0x99, 3, 7).hex()
got = unpoke_code.code_pointers({'%08X' % table: drawn, '0C800000': drawn}, img, BASE, spans)
w = words(got['%08X' % table])
if w[:2] != [0x0C010000, 0x8C010040]:
    bad.append('table/mirror: %r' % [hex(x) for x in w])
if w[2] != 0x99:
    bad.append('table data word changed: %r' % [hex(x) for x in w])
if w[3] != 0x0C010050:
    bad.append('middle: %r' % [hex(x) for x in w])
if w[4] != 7:
    bad.append('one past the end restored: %r' % [hex(x) for x in w])
if got['0C800000'] != drawn:
    bad.append('outside: %r' % got['0C800000'])
odd = unpoke_code.code_pointers({'%08X' % (table + 2): 'ffff' + struct.pack('<I', 0xAAAAAAAA).hex()}, img, BASE, spans)
if odd['%08X' % (table + 2)] != 'ffff' + img[table - BASE + 4:table - BASE + 8].hex():      # the whole word at table+4 is a code address
    bad.append('edges: %r' % odd)
# same_fault: every case of the named file marked, nothing else in it changed
import json  # noqa: E402
import tempfile  # noqa: E402
d = {'dev': [{'about': 'case 0', 'regs': {'r4': '0C800000'}}], 'holdout': [{'about': 'case 1'}]}
t = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
json.dump(d, t)
t.close()
unpoke_code.mark_same_fault(t.name)
m = json.load(open(t.name))
os.unlink(t.name)
if not all(c.get('same_fault') is True for v in m.values() for c in v) or m['dev'][0]['regs'] != {'r4': '0C800000'}:
    bad.append('same_fault: %r' % m)
# drop_faulting: the cases on which the original stops go, the rest stay in order (a stand-in for sh4sim.run)
d = {'dev': [{'about': 'case 0'}, {'about': 'case 1', 'regs': {'r4': '9'}}], 'holdout': [{'about': 'case 2'}]}
t = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
json.dump(d, t)
t.close()
seen = []


def run(case, _dir):
    seen.append((case['entry'], case['end'], case['exe']))
    return {'error': 'unaligned 2-byte read at 00000009' if case.get('regs') else None}


n = unpoke_code.drop_faulting(t.name, 0x0C010000, 0x0C010012, run)
m = json.load(open(t.name))
os.unlink(t.name)
if n != 1 or [c['about'] for c in m['dev']] != ['case 0'] or [c['about'] for c in m['holdout']] != ['case 2']:
    bad.append('drop_faulting: %r %r' % (n, m))
if seen and seen[0] != ('0C010000', '0C010012', '1ST_READ.BIN'):
    bad.append('drop_faulting run: %r' % (seen[0],))
if any('exe' in c or 'entry' in c for v in m.values() for c in v):
    bad.append('drop_faulting wrote the run fields into the cases: %r' % m)
if bad:
    sys.exit('[ERROR] unpoke check failed:\n' + '\n'.join(bad))
print('[unpoke] ok: jump-table words keep the image values, data words and outside pokes stay as drawn, same_fault marks, cases the original faults on dropped')
