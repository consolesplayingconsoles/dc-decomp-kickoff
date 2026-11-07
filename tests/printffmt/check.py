#!/usr/bin/env python3
"""A call to nlPrintf is compared on its format string and the words the format consumes, not on all four words its definition declares
(scripts/tools/equiv.py, callview). No game data, no compiler. Stdlib only.

nlPrintf is declared `Stk4 s`, so a call was compared on four stack words. A format with two conversions reads two arguments; the fourth
word is a leftover: in Zombie Revenge FUN_0c0c381c it is a local of the caller's own at [sp] (0 in the original, an unwritten word in the
C: the frames differ, the printed text does not).

    check.py      callview on a call with four stored stack words, format strings read from a fake executable:
                    two       "MODEL %d (%s)" consumes 2 words: the call is compared on 3 stack words (format + 2)
                    none      "text only" consumes none: 1 word
                    double    "%f" consumes 2 words (a double): 3 words
                    percent   "100%% %d" consumes 1 word: 2 words
                    star      "%*d" consumes 2 words (width and value): 3 words
                    other     a callee that is not a printf keeps its declared 4 words
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools'))
os.chdir(tempfile.mkdtemp())                       # callview asks the repo for the callee's reads: none here
import toolpath  # noqa: E402,F401
import equiv  # noqa: E402

BASE = 0x0C010000
TO = 0x0C0DB0E0
STRINGS = {0x0C010100: b'MODEL %d (%s)\n', 0x0C010200: b'text only', 0x0C010300: b'%f', 0x0C010400: b'100%% %d', 0x0C010500: b'%*d'}


def words(fmt_addr, name='nlPrintf'):
    exe = bytearray(0x1000)
    for a, s in STRINGS.items():
        exe[a - BASE:a - BASE + len(s)] = s
    equiv.FMT_EXE[:] = [bytes(exe), BASE]
    equiv.STACKN[TO] = 4
    equiv.READS_NAME[TO] = name
    equiv._READS.pop(TO, None)
    sw = ['%08X' % fmt_addr, '00000001', '00000002', '00000003']
    v = equiv.callview('%08X' % TO, ['00000000'] * 4, ['00000000'] * 8, {}, None, [False] * 4, None, None, None, sw, [True] * 4)
    return len(v[1]) - 4                           # the stack words after r4-r7


def main():
    bad = []
    for label, addr, want in (('two', 0x0C010100, 3), ('none', 0x0C010200, 1), ('double', 0x0C010300, 3), ('percent', 0x0C010400, 2), ('star', 0x0C010500, 3)):
        got = words(addr)
        if got != want:
            bad.append('%s: compared on %d stack words, expected %d' % (label, got, want))
    got = words(0x0C010100, name='someOtherFunction')
    if got != 4:
        bad.append('other: a callee that is not a printf is compared on %d stack words, expected its declared 4' % got)
    if bad:
        sys.exit('[ERROR] printffmt check failed:\n' + '\n'.join(bad))
    print('[printffmt] ok: a printf call is compared on its format and the words the format consumes')


if __name__ == '__main__':
    main()
