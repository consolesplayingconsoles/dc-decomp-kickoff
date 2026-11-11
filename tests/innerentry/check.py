#!/usr/bin/env python3
"""A function functions.txt does not list, inside a listed one (scripts/tools/1-2-baseline/checksizes.py --inner;
scripts/tools/5-generated/gen_equiv/gen_core.py inside_of). Zombie Revenge FUN_0c017aca was listed over three functions; FUN_0c018142
reaches the third, 0C017AE2, by `bra`. The generator wrote `((int (*)(int, int))(0xC017AE2))(...)`, the movable build replaced
FUN_0c017aca with its C and sent the address into a trimmed data copy: after the intro video the game ran zeros. No game data, no
compiler. Stdlib only.

    check.py      report   checksizes.py --inner names the start inside the host and the entry that branches to it
                  value    and an entry that keeps the start's address in a pool word without calling it (a callback)
                  refuse   the generator does not write the branch to that address as a call: it skips the caller and names the host
                  start    a branch to the host's own start is still a tail call by name
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda *h: struct.pack('<%dH' % len(h), *h)

CODE = (W(0x4F22, 0x4F26, 0x000B, 0x0009) +       # 0 host: sts.l pr / lds.l pr / rts / nop
        W(0x2FE6, 0x000B, 0x6EF6, 0x0009) +       # 8 inner (listed inside host): mov.l r14,@-r15 / rts / mov.l @r15+,r14 / nop
        W(0xAFFA, 0x0009) +                       # 16 caller: bra 8 (the inner start) / nop
        W(0xAFF4, 0x0009) +                       # 20 plain: bra 0 (the host's start) / nop
        W(0xD401, 0x000B, 0x0009, 0x0009) +       # 24 keeper: mov.l @(32),r4 (the inner start, kept as a value: a callback) / rts / nop
        struct.pack('<I', 0x0C010008))            # 32 its pool word
FUNCS = 'F 0c010000 16 host\nF 0c010010 4 caller\nF 0c010014 4 plain\nF 0c010018 12 keeper\n'


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCS)
        os.makedirs(os.path.join(tmp, 'src'))
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/checksizes.py', '--inner'], cwd=tmp,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if '0c010008 inside host' not in r or 'caller bra' not in r:
            bad.append('report: want 0c010008 inside host, reached from caller bra, got:\n' + r[-400:])
        if 'keeper value' not in r:
            bad.append('value: an address kept in a pool word (a callback, Zombie Revenge FUN_0c0b2fb0) is reported too, got:\n' + r[-400:])
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, gen_pipe.variants(n, False)[0], False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script, 'caller', 'plain'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True, env=dict(os.environ, GEN_FRAME='0')).stdout
        parts = {c.split('\n', 1)[0]: c.split('\n', 1)[1] if '\n' in c else '' for c in out.split('@@@@ ')[1:]}
        if 'SKIPPED' not in parts.get('caller', '') or 'inside host' not in parts.get('caller', ''):
            bad.append('refuse: the caller should be skipped naming host, got:\n' + parts.get('caller', out[-400:]))
        if 'SKIPPED' in parts.get('plain', 'SKIPPED') or 'host(' not in parts.get('plain', ''):
            bad.append('start: a branch to the host\'s start should be a tail call to host, got:\n' + parts.get('plain', out[-400:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for b in bad:
        print('FAIL', b)
    print('innerentry: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
