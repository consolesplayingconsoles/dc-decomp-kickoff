#!/usr/bin/env python3
"""A drawn case whose outcome depends on registers the function never set (scripts/tools/5-generated/gen_equiv/directed.py
unset_dependent), with the real simulator on synthetic code. No game data, no compiler. Stdlib only.

Virtua Tennis shopDrawCatPanel picks an index from a4 by a chain of compares (1, 6, 2, 0, 4, 5) into r10 and leaves r10 untouched for
any other a4: the original then indexes with the caller's r10, the C with an uninitialised variable. A case drawn with such an a4 is
no input the game makes, and the two sides read different words. unset_dependent runs the original twice with different incoming
r8-r14: when what it does differs, the case depends on them and is dropped.

    check.py      reads    stores the incoming r10 to memory: dependent
                  sets     sets r10 first, then stores it: not dependent
                  freads   stores the incoming fr12: dependent
                  fcall    passes the incoming fr12 to a call as fr4 (endingSceneDraw, Virtua Tennis: fr12 set on other paths only):
                           dependent
                  aftercall  stores r5 after a call (a caller-saved register the callee may change: entryGridDrawCursors, Virtua
                           Tennis, a colour from r5 after mathLerp on a path that never sets it): dependent
                  result   stores r0 after a call (the call's result): not dependent
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated', 'gen_equiv'), os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import directed  # noqa: E402

BASE = 0x8C010000


def main():
    bad = []
    d = tempfile.mkdtemp()
    try:
        for name, first, store, want in (('reads', 0x0009, 0x21A2, True), ('sets', 0xEA05, 0x21A2, False), ('freads', 0x0009, 0xF1CA, True)):
            code = [first,               # nop, or mov #5,r10
                    0xD102,              # mov.l @(pool),r1
                    store,               # mov.l r10,@r1 / fmov.s fr12,@r1
                    0x000B, 0x0009,      # rts / nop
                    0x0009]
            body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
            open(os.path.join(d, name + '.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
            run = lambda c, n=name: sh4sim.run(dict(c, exe=n + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xA),
                                                    steps=2000), d)
            try:
                got = directed.unset_dependent({}, run)
            except AttributeError:
                sys.exit('[ERROR] unsetregs check failed:\ndirected.py has no unset_dependent()')
            if got != want:
                bad.append('%s: dependent %s, want %s' % (name, got, want))
        code = [0x4F22, 0xF4CC,      # sts.l pr / fmov fr12,fr4
                0xB003, 0x0009,      # bsr f / nop
                0x4F26, 0x000B, 0x0009,      # lds.l @r15+,pr / rts / nop
                0x000B, 0x0009]      # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in code)
        open(os.path.join(d, 'fcall.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        run = lambda c: sh4sim.run(dict(c, exe='fcall.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xE), steps=2000), d)
        if not directed.unset_dependent({}, run):
            bad.append('fcall: a call given the incoming fr12 is not dependent')
        for name, reg, want in (('aftercall', 5, True), ('result', 0, False)):
            code = [0x4F22, 0xE509,      # sts.l pr / mov #9,r5
                    0xB005, 0x0009,      # bsr f / nop
                    0xD103,              # mov.l @(pool),r1
                    0x2102 | (reg << 4), # mov.l rN,@r1
                    0x4F26, 0x000B, 0x0009,      # lds.l @r15+,pr / rts / nop
                    0x000B, 0x0009,      # f: rts / nop
                    0x0009]
            body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
            open(os.path.join(d, name + '.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
            run = lambda c, n=name: sh4sim.run(dict(c, exe=n + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x12),
                                                    steps=2000), d)
            for case in ({'calls': [{'r0': '00000007'}]}, {}):          # with an answer, and with none (each call then returns 0)
                got = directed.unset_dependent(case, run)
                if got != want:
                    bad.append('%s%s: dependent %s, want %s' % (name, '' if case else ' (no answers)', got, want))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] unsetregs check failed:\n' + '\n'.join(bad))
    print('[unsetregs] ok: a case whose outcome depends on registers the function never set is told apart')


if __name__ == '__main__':
    main()
