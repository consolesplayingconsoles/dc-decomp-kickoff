#!/usr/bin/env python3
"""The generator's case growth never pokes the function's own bytes (scripts/tools/5-generated/gen_equiv/gen_drv.py grow), whichever
mirror of RAM the game is linked at. grow takes the words the original read last as the ones its final guard looked at and sets them;
the function's own jump table is one of those reads, and a case that rewrites it is no input the compiled C can follow (the original
jumps elsewhere, the switch in the C does not): Virtua Tennis commonLoadStep, linked at 8C...: `poke 0C0DD830` into its own table, a
return value of 1 against 5. The simulator reports reads at 0C..., the window was compared against the start from functions.txt
(8C... on that game, 0C... on Crazy Taxi), so it never matched there. No game data, no compiler. Stdlib only.

    check.py      original_runs replaced by a stand-in that reports a read inside the function's own bytes, in the simulator's
                  0C... form, and a read far outside it:
                    cx   functions.txt at 0C... (Crazy Taxi): no case grow tries pokes inside the function's bytes
                    vt   functions.txt at 8C... (Virtua Tennis): the same
                    out  a read outside the function is still set (the guard is not simply switched off)
"""
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
FORM = sys.argv[1] if len(sys.argv) > 1 else ''
if not FORM:
    # one process per form: the generator reads functions.txt when it is imported
    import subprocess
    bad = []
    for form, base in (('cx', '0c020000'), ('vt', '8c020000')):
        r = subprocess.run([sys.executable, os.path.abspath(__file__), form], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True)
        if r.returncode:
            bad.append('%s (functions.txt at %s): %s' % (form, base, r.stdout.strip()[-400:]))
    if bad:
        sys.exit('[ERROR] draw mirror check failed:\n' + '\n'.join(bad))
    print('[drawmirror] ok: growth never pokes the function\'s own bytes, linked at 0C... or at 8C..., and still sets words outside them')
    sys.exit(0)

BASEADDR = {'cx': '0c020000', 'vt': '8c020000'}[FORM]
tmp = tempfile.mkdtemp()
os.chdir(tmp)
open('functions.txt', 'w').write('F %s 64 fn\n' % BASEADDR)
open('BASE', 'w').write(BASEADDR.upper() + '\n')
open('1ST_READ.BIN', 'wb').write(b'\x00\x09' * 32)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import gen_drv  # noqa: E402

OWN = 0x0C020010          # inside the function (its jump table), as the simulator reports it
FAR = 0x0C800000          # a word of game state
seen = []


def standin(name, case):
    seen.append(case)
    gen_drv.LAST_READS[:] = [FAR, OWN]
    return 10, {len(seen) % 7, len(seen)}


gen_drv.original_runs = standin
rng = random.Random(1)
start = [{'about': 'case 0', 'regs': {'r4': '00000001'}, 'poke': {}, 'calls': []}]
gen_drv.LAST_READS[:] = [FAR, OWN]
gen_drv.grow('fn', [(start[0], 10, {1})], [0, 1, 2, 5], rng, [0, 1, 2, 5], budget=200)

inside = [k for c in seen for k in c.get('poke', {}) if 0x0C020000 <= (0x0C000000 | (int(k, 16) & 0x1FFFFFFF)) < 0x0C020040]
outside = [k for c in seen for k in c.get('poke', {}) if (int(k, 16) & 0x1FFFFFFF) == (FAR & 0x1FFFFFFF)]
if inside:
    sys.exit('growth poked the function\'s own bytes: %s' % sorted(set(inside))[:4])
if not outside:
    sys.exit('growth no longer sets a word outside the function (%d cases tried)' % len(seen))
