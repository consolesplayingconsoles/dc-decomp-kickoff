#!/usr/bin/env python3
"""The SDK source files that reproduce whole are written as C units a build can take (scripts/tools/5-generated/sdk_source.py units()).
The units of Sonic Adventure and Crazy Taxi were laid out by hand on 2026-11-14 (sg_syBrd.c: build MATCH in both); the first try
failed on headers the build could not see and on an include folder with a hyphen in its name. No game data, no compiler. Stdlib only.

    check.py      a temp repo: functions.txt lists a1, a2, b1, b2, c1 in that order; the staged tree holds
                    A_.C   defines a1 and a2, both verified, one run: a unit, range a1..b1, the header line, its `..\\inc\\X.H` include
                           cut to X.H, the private header copied to build/sdkpriv and the SDK's to build/sdkinc
                    B.c    defines b1 and b2, only b1 verified: in part, no unit
                    C.c    defines c1 (verified) and zz, which functions.txt does not list: a unit of one function
                  A's link has constants a literal of a1 points into (their range goes in the unit's first line, @data) and
                  variables nothing points into (named in a second line as not placed)
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))


def main():
    tmp = tempfile.mkdtemp(prefix='sdkunits_')
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.chdir(tmp)
        open('functions.txt', 'w').write('F 8c010000 8 a1\nF 8c010008 8 a2\nF 8c010010 8 b1\nF 8c010018 8 b2\nF 8c010020 8 c1\nD 8c010028 4 tail\n')
        work = os.path.join('build', 'sdk-source', 'work')
        for d in ('t0/lib', 't0/inc', 'sdkinc0'):
            os.makedirs(os.path.join(work, d))
        fn = lambda n: 'int %s(int a)\n{\n    return a;\n}\n' % n
        A = os.path.join(work, 't0', 'lib', 'A_.C')
        B = os.path.join(work, 't0', 'lib', 'B.c')
        C = os.path.join(work, 't0', 'lib', 'C.c')
        open(A, 'w').write('#include <shinobi.h>\n#include "..\\inc\\X.H"\n' + fn('a1') + fn('a2'))
        open(B, 'w').write(fn('b1') + fn('b2'))
        open(C, 'w').write(fn('c1') + fn('zz'))
        open(os.path.join(work, 't0', 'inc', 'X.H'), 'w').write('/* private */\n')
        open(os.path.join(work, 'sdkinc0', 'shinobi.h'), 'w').write('/* sdk */\n')
        sys.path.insert(0, os.path.join(tmp, 'tools', '5-generated'))
        sys.path.insert(0, os.path.join(tmp, 'tools'))
        import sdk_source
        import struct
        # A's link: P at 0E100000, constants (C) at 0E100010 for 8 bytes, variables (B) at 0E100018 for 4. a1's code holds a literal
        # pointing 4 bytes into C; the game's a1 holds 8C010014 there: C starts at 8C010010, inside the executable. Nothing points into B.
        mp = ("P                                 H'0E100000  -  H'0E10000F  H'00000010\n"
              "C                                 H'0E100010  -  H'0E100017  H'00000008\n"
              "B                                 H'0E100018  -  H'0E10001B  H'00000004\n"
              "_a1                               H'0E100000               ENT\n")
        code = struct.pack('<2HI', 0x0009, 0x000B, 0x0E100014) + b'\0' * 20
        exe = struct.pack('<2HI', 0x0009, 0x000B, 0x8C010014) + b'\0' * 24
        # the literal sits in the pool after a1's 4 bytes of code, before the next entry: read too
        got = sdk_source.data_places(code, mp, exe, 0x8C010000, {'a1': [(0x8C010000, 4)], 'a2': [(0x8C010008, 8)]}, ['a1'])
        if got != {'C': (8, {0x8C010010}), 'B': (4, set())}:
            sys.exit('[ERROR] sdkunits check failed: data_places gave %r' % (got,))
        sdk_source.DATA[A] = got
        # constants nothing points at (a build string) are found in the game by their bytes, when they are there once
        code2 = struct.pack('<2HI', 0x0009, 0x000B, 0) + b'\0' * 8 + b'BUILD-ID'
        exe2 = struct.pack('<2HI', 0x0009, 0x000B, 0) + b'\0' * 40 + b'BUILD-ID' + b'\0' * 8
        got2 = sdk_source.data_places(code2, mp.replace("B                                 H'0E100018  -  H'0E10001B  H'00000004\n", ''), exe2, 0x8C010000, {'a1': [(0x8C010000, 8)]}, ['a1'])
        if got2 != {'C': (8, {0x8C010030})}:
            sys.exit('[ERROR] sdkunits check failed: constants found by their bytes gave %r' % (got2,))
        whole, part = sdk_source.units({'a1': (A, ''), 'a2': (A, ''), 'b1': (B, ''), 'c1': (C, '')})
        bad = []
        if sorted(whole) != [('A', 2, 0x8C010000, 0x8C010010), ('C', 1, 0x8C010020, 0x8C010028)]:
            bad.append('whole files: %r' % (sorted(whole),))
        if part != [('B.c', 1, 2)]:
            bad.append('files in part: %r, want B.c with 1 of 2' % (part,))
        u = os.path.join('sdk-source', 'units', 'A.c')
        t = open(u).read() if os.path.exists(u) else ''
        if not t.startswith('/* @unit 8C010000-8C010010 @data 8C010010-8C010018 -include=build\\sdkinc,build\\sdkpriv,src */\n/* data not placed: B (4 bytes).'):
            bad.append('unit header: %r' % t[:90])
        if '#include "X.H"' not in t or '..\\inc' in t:
            bad.append('an include written with a path is not cut to its file name')
        if os.path.exists(os.path.join('sdk-source', 'units', 'B.c')):
            bad.append('a file that reproduces in part got a unit')
        if not os.path.exists(os.path.join('build', 'sdkpriv', 'X.H')) or not os.path.exists(os.path.join('build', 'sdkinc', 'shinobi.h')):
            bad.append('the header folders build/sdkinc and build/sdkpriv are not filled')
        if bad:
            sys.exit('[ERROR] sdkunits check failed:\n' + '\n'.join(bad))
        print('[sdkunits] ok: a source file that reproduces whole becomes a unit with its range and header folders; one in part does not')
    finally:
        os.chdir(SKILL)
        shutil.rmtree(tmp, ignore_errors=True)


main()
