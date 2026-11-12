#!/usr/bin/env python3
"""A function whose code begins before its entry (functions.txt `B <start> <size> <name>`; scripts/tools/sh4sim.py body_before,
scripts/tools/5-generated/gen_equiv/gen_core.py BODY). SHC can lay a loop's body out above the function's address and enter at the loop
test: Zombie Revenge FUN_0c016d20 has its body at 0C016CE0 and its entry at 0C016D20. Listed from the entry only, the `bt` back up read as
a jump out of the function: the generated C called its own loop body as another function, the check passed it (the original jumped out
too), and the movable build sent that call into a data copy. No game data, no compiler. Stdlib only.

    check.py      f: body (add #1,r5; add #-1,r4) at +0, entry (tst r4,r4; bf body; rts; mov r5,r0) at +4, run with r4 = 3:
                    with `B`     the loop runs in the function: no call out, r5 counted up three times, the body in the covered addresses
                    without      the bf back up is a jump out of the function (what the check saw before)
                    written      the generated C of f is a loop with no call: the body falls into the entry, the loop test (gen_cfg.succ_of
                                 by address, gen_core's walk running on into its own code), not a call to f or to the body's address
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools'))
import sh4sim  # noqa: E402

BASE = 0x0C010000


def main():
    code = b''.join(struct.pack('<H', w) for w in (0x7501, 0x74FF, 0x2448, 0x8BFB, 0x000B, 0x6053))
    entry, end = BASE + 4, BASE + len(code)
    tmp = tempfile.mkdtemp(prefix='bodybefore_')
    try:
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % entry, 'end': '%08X' % end,
                'regs': {'r4': '00000003'}, 'steps': 1000}
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 8 f\nB %08x 4 f\n' % (entry, BASE))
        r = sh4sim.run(dict(case), tmp)
        assert r['error'] is None, 'with B: %s' % r['error']
        assert not r['calls'], 'with B, the loop body is still a jump out: %r' % r['calls']
        assert r['steps'] >= 3 * 4, 'with B, the loop did not run three times (%d steps)' % r['steps']
        assert BASE in r.get('covered', []) and BASE + 2 in r.get('covered', []), 'with B, the body is not in the covered addresses: %r' % r.get('covered')
        os.utime(os.path.join(tmp, 'functions.txt'), None)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 8 f\n' % entry)
        os.utime(os.path.join(tmp, 'functions.txt'), (1, 1))      # a different mtime: the list is read again
        r = sh4sim.run(dict(case), tmp)
        assert r['calls'] and r['calls'][0]['to'] == '%08X' % BASE, 'without B, the branch back up is not a jump out: %r' % r['calls']
        shutil.copytree(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools'), os.path.join(tmp, 'tools'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 8 f\nB %08x 4 f\n' % (entry, BASE))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('f', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        assert 'SKIPPED' not in out and 'Traceback' not in out, 'written: %s' % out
        body = out[out.index('{'):]
        assert 'f(' not in body and '0xC010000' not in body.upper().replace('0X', '0x') and ('for (' in body or 'while' in body or 'goto' in body), \
            'written: the C of f calls itself or its body instead of looping:\n%s' % out
        print('[bodybefore] ok: code listed before a function\'s entry runs as its own; without the B line it is a jump out; the generated C loops')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


main()
