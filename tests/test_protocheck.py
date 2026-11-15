#!/usr/bin/env python3
"""A call that passes fewer arguments than its callee takes (scripts/tools/8-build/protocheck.py). No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/def.c (the callee's definition), src/short.c and src/full.c:
                    short     a file that prototypes `g(int, float)` for the definition `g(int a4, Stk3 p, float f4)` and calls it
                              directly is reported with 0 words against 3 (Virtua Tennis selPanelDraw: called without its position)
                    full      a file that prototypes all of it is not reported
                    cast      a call through a function-pointer cast is not looked at
                    variadic  a definition with `...` is left alone
                    ints      five integer parameters take one stack word, so a prototype of four is short by one
                  --reads (the registers the original reads against the registers a definition declares; the reads are given, no game data):
                    passed on  cpuDblThinkAll-like `(float, float, float)` against reads r6 r7 fr5 fr6 fr7 is reported for r6, r7 and fr7
                    exact      a definition that declares every register read, a structure in the list (stack) and a function with no reads are not
                    unknown    a function whose reads are not known (None) and a variadic definition are left alone
                    gap        reading r6 with one integer parameter reports r6 (and not r5, which is not read)
                  the argument registers (scan_regs), in a second temp repo:
                    old        `int one(void);` against the definition `int one(int a4)`, called, is reported with (0, 0) against (1, 0)
                               (Virtua Tennis uniformPreviewFree: nlObjPutFreeTextureOnce() with no model)
                    floats     `int fl(int, float);` against `(int a4, float f4, float f5)` is reported on the float register
                    nodef      a callee src/ does not define is compared against the file that prototypes the most
                    empty      `int empty();` says nothing and is left alone; a file with the full prototype is not reported
                  the calls that lost an argument (scan_lost; the original's call sites are given, no game data):
                    set        c1 calls one() and the original writes r4 before the call: reported; nodef the same
                    not set    c2 calls one() and the original writes nothing before it: not reported
                    unused     the callee's C never uses the parameter: not reported
                    float      fl is short on a float register only: not reported (integer registers only)
                  the call sites of the original (sites), on a 0x110-byte executable assembled here by hand:
                    r4         `mov #5,r4` before `jsr @r3` gives the callee with r4; r3, the address, is not counted
                    mova       `mova @(..,pc),r0` writes r0 (its bits name r7)
                    none       nothing written before the call gives an empty set
"""
import unittest
from unittest import mock
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

DEF_C = ("typedef struct { int w[3]; } Stk3;\nint g(int a4, Stk3 p, float f4)\n{\n    return a4;\n}\n\n"
         "int five(int a4, int a5, int a6, int a7, int a8)\n{\n    return a8;\n}\n\n"
         "int va(int a4, ...)\n{\n    return a4;\n}\n")
SHORT_C = ("int g(int, float);\nint five(int, int, int, int);\nint va(int);\nvoid h(void)\n{\n    g(1, 2.0f);\n    five(1, 2, 3, 4);\n    va(1);\n}\n")
FULL_C = ("typedef struct { int w[3]; } Stk3;\nint g(int, Stk3, float);\nint five(int, int, int, int, int);\nvoid k(void)\n{\n"
          "    g(1, *(Stk3 *)0, 2.0f);\n    five(1, 2, 3, 4, 5);\n}\n")
CAST_C = ("int g(int, float);\nvoid c(void)\n{\n    ((int (*)(int, Stk3, float))(g))(1, *(Stk3 *)0, 2.0f);\n}\n")


READS_C = ("typedef struct { int w[3]; } Stk3;\n"
           "int thinkAll(float f4, float f5, float f6)\n{\n    return 0;\n}\n\n"
           "int exact(int a4, int a5, float f4, float f5)\n{\n    return a4;\n}\n\n"
           "int structy(int a4, Stk3 p, float f4)\n{\n    return a4;\n}\n\n"
           "int quiet(void)\n{\n    return 0;\n}\n\n"
           "int unknown(int a4)\n{\n    return a4;\n}\n\n"
           "int va(int a4, ...)\n{\n    return a4;\n}\n\n"
           "int gap(int a4)\n{\n    return a4;\n}\n")
READS = {'thinkAll': frozenset(['r6', 'r7', 'fr5', 'fr6', 'fr7']), 'exact': frozenset(['r4', 'r5', 'fr4', 'fr5']),
         'structy': frozenset(['r4', 'fr4']), 'quiet': frozenset(), 'unknown': None, 'va': frozenset(['r4', 'r7']), 'gap': frozenset(['r4', 'r6'])}


def reads_check(tmp):
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    open(os.path.join(tmp, 'src', 'reads.c'), 'w').write(READS_C)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/8-build'); import protocheck\n"
              "R = %r\nfor n, f, miss, pl in sorted(protocheck.scan_reads(reads_of=R.get)):\n    print(n, ' '.join(miss))\n" % READS)
    out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
    got = sorted(out.strip().split('\n')) if out.strip() else []
    want = ['gap r6', 'thinkAll r6 r7 fr7']
    if got != want:
        sys.exit('[ERROR] protocheck --reads check failed: got %s, want %s' % (got, want))


REGS_DEF = ("int one(int a4)\n{\n    return a4;\n}\n\nint unused(int a4)\n{\n    return 0;\n}\n\n"
            "int fl(int a4, float f4, float f5)\n{\n    return a4;\n}\n\nint empty(int a4)\n{\n    return a4;\n}\n")
REGS_OLD = ("int one(void);\nint unused(void);\nint fl(int, float);\nint nodef(void);\nint empty();\n"
            "void c1(void)\n{\n    one();\n    unused();\n    fl(1, 2.0f);\n    nodef();\n    empty();\n}\n\nvoid c2(void)\n{\n    one();\n}\n")
REGS_NEW = "int one(int);\nint nodef(int);\nvoid c3(void)\n{\n    one(1);\n    nodef(1);\n}\n"
SITES = {'c1': [('one', frozenset(['r4'])), ('unused', frozenset(['r4'])), ('fl', frozenset(['r4'])), ('nodef', frozenset(['r4']))],
         'c2': [('one', frozenset())], 'c3': [('one', frozenset(['r4'])), ('nodef', frozenset(['r4']))]}
IMPORT = "import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/8-build'); import protocheck\n"


def py(tmp, script):
    out = subprocess.run([sys.executable, '-c', IMPORT + script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
    return sorted(out.strip().split('\n')) if out.strip() else []


def exe():
    """(1ST_READ.BIN, functions.txt): three callers of g at 8c010100, each `<first> ; mov.l @(pool,pc),r3 ; jsr @r3 ; nop ; rts ; nop ; pool`"""
    import struct
    b = bytearray(0x110)
    for off, first in ((0x00, 0xE405), (0x20, 0x0009), (0x40, 0xC700)):          # mov #5,r4 / nop / mova @(0,pc),r0
        struct.pack_into('<6HI', b, off, first, 0xD302, 0x430B, 0x0009, 0x000B, 0x0009, 0x8C010100)
    # f_pool at +60: a pool word that decodes as `mov #5,r4` (E405) sits before the call, loaded by the code above it: data, no write
    struct.pack_into('<4H', b, 0x60, 0xD101, 0xA003, 0x0009, 0x0009)
    struct.pack_into('<2H', b, 0x68, 0xE405, 0xE405)
    struct.pack_into('<6HI', b, 0x6C, 0xD302, 0x430B, 0x0009, 0x000B, 0x0009, 0x0009, 0x8C010100)
    # f_data at +80: a word no code loads or reaches (E405, `mov #5,r4` if it were code) behind a bra: data, no write
    struct.pack_into('<3H', b, 0x80, 0xA001, 0x0009, 0xE405)
    struct.pack_into('<5HI', b, 0x86, 0xD302, 0x430B, 0x0009, 0x000B, 0x0009, 0x8C010100)
    struct.pack_into('<2H', b, 0x100, 0x000B, 0x6043)                              # g: rts ; mov r4,r0
    return bytes(b), 'F 8c010000 16 f_set\nF 8c010020 16 f_none\nF 8c010040 16 f_mova\nF 8c010060 28 f_pool\nF 8c010080 20 f_data\nF 8c010100 4 g\n'


def regs_check(tools):
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(tools, os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'src'))
        for n, t in (('def', REGS_DEF), ('old', REGS_OLD), ('new', REGS_NEW)):
            open(os.path.join(tmp, 'src', n + '.c'), 'w').write(t)
        got = py(tmp, "for n, f, calls, p, r, rf in protocheck.scan_regs():\n    print(n, f, calls, p, r, rf)\n")
        want = ['fl src/old.c 1 (1, 1) (1, 2) src/def.c', 'nodef src/old.c 1 (0, 0) (1, 0) src/new.c', 'one src/old.c 2 (0, 0) (1, 0) src/def.c',
                'unused src/old.c 1 (0, 0) (1, 0) src/def.c']
        if got != want:
            sys.exit('[ERROR] protocheck register check failed: got %s, want %s' % (got, want))
        got = py(tmp, "S = %r\nfor c, f, n, regs in protocheck.scan_lost(sites_of=S.get):\n    print(c, f, n, ' '.join(regs))\n" % SITES)
        want = ['c1 src/old.c nodef r4', 'c1 src/old.c one r4']
        if got != want:
            sys.exit('[ERROR] protocheck lost-argument check failed: got %s, want %s' % (got, want))
        # a callee with no C anywhere (lib, prototyped (void) in old.c): the registers are what its original reads at its entry
        open(os.path.join(tmp, 'src', 'old.c'), 'a').write('\nint lib(void);\nint c9(int a)\n{\n    return lib();\n}\n')
        got = py(tmp, "S = dict(%r, c9=[('lib', frozenset(['r4', 'r5']))])\nR = {'lib': set(['r4', 'r5'])}\n"
                      "for c, f, n, regs in protocheck.scan_lost(sites_of=S.get, reads_of=R.get):\n    if n == 'lib':\n        print(c, f, n, ' '.join(regs))\n" % SITES)
        if got != ['c9 src/old.c lib r4 r5']:
            sys.exit('[ERROR] protocheck lost-argument check failed for a callee with no C: got %s' % got)
        got = py(tmp, "S = dict(%r, c9=[('lib', frozenset(['r5']))])\nR = {'lib': set(['r4'])}\n"
                      "print(len([1 for c, f, n, regs in protocheck.scan_lost(sites_of=S.get, reads_of=R.get) if n == 'lib']))\n" % SITES)
        if got != ['0']:
            sys.exit('[ERROR] protocheck lost-argument check failed: a register the callee reads but the original does not write before the call is reported')
        got = py(tmp, "S = %r\nprint(len([1 for c, f, n, regs in protocheck.scan_lost(sites_of=S.get, reads_of={'nodef': set()}.get) if n == 'nodef']))\n" % SITES)
        if got != ['0']:
            sys.exit('[ERROR] protocheck lost-argument check failed: a callee with no C whose original reads no argument is reported from a wider prototype')
        got = py(tmp, "S = %r\nprint(len([1 for c, f, n, regs in protocheck.scan_lost(sites_of=S.get, reads_of={'one': set()}.get) if n == 'one']))\n" % SITES)
        if got != ['0']:
            sys.exit('[ERROR] protocheck lost-argument check failed: a callee whose definition declares a parameter its original never reads is reported')
        if py(tmp, "print(len(protocheck.scan_lost()))\n") != ['0']:
            sys.exit('[ERROR] protocheck lost-argument check failed: a repo with no executable reports calls')
        binary, functions = exe()
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(binary)
        open(os.path.join(tmp, 'BASE'), 'w').write('8c010000\n')
        open(os.path.join(tmp, 'functions.txt'), 'w').write(functions)
        got = py(tmp, "for n in ('f_set', 'f_none', 'f_mova', 'f_pool', 'f_data'):\n    print(n, [(c, sorted(w)) for c, w in protocheck.sites(n)])\n")
        want = ["f_data [('g', [])]", "f_mova [('g', ['r0'])]", "f_none [('g', [])]", "f_pool [('g', ['r1'])]", "f_set [('g', ['r4'])]"]
        if got != want:
            sys.exit('[ERROR] protocheck call-site check failed: got %s, want %s' % (got, want))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestProtocheck(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_protocheck(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            os.makedirs(os.path.join(tmp, 'src'))
            for n, t in (('def', DEF_C), ('short', SHORT_C), ('full', FULL_C), ('cast', CAST_C)):
                open(os.path.join(tmp, 'src', n + '.c'), 'w').write(t)
            script = ("import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/8-build'); import protocheck\n"
                      "for n, f, calls, pw, dw in sorted(protocheck.scan()):\n    print(n, f, calls, pw, dw)\n")
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
            got = sorted(out.strip().split('\n')) if out.strip() else []
            want = ['five src/short.c 1 0 1', 'g src/short.c 1 0 3']
            if got != want:
                self.fail('[ERROR] protocheck check failed: got %s, want %s' % (got, want))
            reads_check(tmp)
            regs_check(os.path.join(SKILL, 'scripts', 'tools'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
