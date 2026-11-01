#!/usr/bin/env python3
"""The generator restores SR from the value it saved, not from SR as it is at the restore (scripts/tools/5-generated/gen_equiv/gen_core.py).
No game data, no compiler. Stdlib only.

An SR read by stc was written as `_builtin_get_cr()` where it is used. For a function that saves SR, sets the block bit and later puts
the saved word back (Virtua Tennis FUN_8c0f8100, the interrupt setup), the restore became `_builtin_set_cr(_builtin_get_cr() & ...)`:
SR read at the end, after the block bit was set, so the bit stayed set ("sr: original 40000000 / C 50000000").

    check.py      f: stc sr,r1 / mov.l @(pool),r2 (0x10000000) / mov r1,r3 / or r2,r3 / ldc r3,sr / ldc r1,sr / rts / nop
                    saved    the restore uses a variable read from SR before the first set_cr, not a get_cr() after it
                    plain    a function that only sets the block bit (stc / or / ldc, no restore) is written as before:
                             _builtin_set_cr((_builtin_get_cr() & 0xFFFFFFFF) | 0x10000000)
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

# stc sr,r1 / mov.l @(12,pc),r2 / mov r1,r3 / or r2,r3 / ldc r3,sr / ldc r1,sr / rts / nop / pool 0x10000000
SAVED = W([0x0102, 0xD203, 0x6313, 0x232B, 0x430E, 0x410E, 0x000B, 0x0009]) + struct.pack('<I', 0x10000000)
# stc sr,r3 / mov.l @(8,pc),r2 / or r2,r3 / ldc r3,sr / rts / nop / pool 0x10000000
PLAIN = W([0x0302, 0xD202, 0x232B, 0x430E, 0x000B, 0x0009]) + struct.pack('<I', 0x10000000)


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(SAVED + PLAIN)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d savedfn\nF %08x %d plainfn\n' % (BASE, len(SAVED), BASE + len(SAVED), len(PLAIN)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, 'void', False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script, 'savedfn', 'plainfn'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        parts = dict(p.split('\n', 1) for p in out.split('@@@@ ')[1:])
        saved, plain = parts.get('savedfn', ''), parts.get('plainfn', '')
        sets = re.findall(r'_builtin_set_cr\((.*)\);', saved)
        if len(sets) != 2:
            bad.append('saved: expected two set_cr, got %r\n%s' % (sets, saved))
        else:
            m = re.search(r'(t\d+) = _builtin_get_cr\(\);', saved)
            if not m or m.start() > saved.index('_builtin_set_cr('):
                bad.append('saved: no variable read from SR before the first set_cr\n%s' % saved)
            elif m.group(1) not in sets[1] or '_builtin_get_cr' in sets[1]:
                bad.append('saved: the restore is %r, want the saved variable %s\n%s' % (sets[1], m.group(1), saved))
        if '_builtin_set_cr((_builtin_get_cr() & 0xFFFFFFFF) | 0x10000000);' not in plain:
            bad.append('plain: changed\n%s' % plain)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] srsave check failed:\n' + '\n'.join(bad))
    print('[srsave] ok: an SR restore uses the word saved before SR changed')


if __name__ == '__main__':
    main()
