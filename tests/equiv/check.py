#!/usr/bin/env python3
"""What the checker (scripts/tools/equiv.py) compares a call on, with no game data and no compiler. Stdlib only.

    check.py      a temp repo with the tools tree, a C file that declares its callees with too few arguments, and their proven
                  definitions in another file of src/:
                    dropped   a call is compared on every argument the callee's definition takes, not only the ones the caller's
                              own prototype names: a caller that drops one fails (InitSys -> nlSetIntrFunction dropped the
                              interrupt callback, VSklSfPlay -> VSklIpPlay two registers and two stack words: both passed and
                              crashed the build from C, Crazy Taxi)
                    floatptr  a float pointer parameter is an integer argument (r4-r7), not a float one
                    stack     arguments past the fourth in the definition are compared on the stack too
                    pointer   a call through a pointer is compared on every argument register this side set from r4, not only
                              the count its own cast names: a caller whose cast and call both drop one fails (nlSetIntrFunction
                              passed the interrupt callback one argument instead of two and booted into a crash, Crazy Taxi)
                    mirror    a game linked at the cached mirror (8C...) is compared like one linked at 0C...: the call the checker
                              sees is normalised to 0C, so the callee's argument count must be found under that address too (a
                              1-argument callee was compared on r5-r7 leftovers, Virtua Tennis)
                    nodecl    a callee the caller's file never prototypes (`extern int f();`, as the generated files declare library
                              calls) still has its stack words compared: the registers were already all compared, the stack was not
                              (Crazy Taxi: navi_GetRouteTbl called getNearLineIndex without its pushed fifth argument, the nearest road
                              line was measured from a stack leftover, the destination arrow led down wrong streets)
                    variadic  a callee the caller's file prototypes as `(int, ...)` is compared on the arguments its definition
                              READS, not on the first one only (Crazy Taxi: kmCreateTABuffer called kmiSetTAEnvironment with 2 of
                              6 arguments); one whose definition reads only its stack word (a printf-style function: the
                              registers are leftovers) is compared on that word alone (mwRnaErrCallFunc, ADXERR_CallErrFunc:
                              their callers differed on leftover r4/r5)
                    leftover  a stack word the caller did not write since its last call is a leftover, not an argument: a call is
                              compared on it only when the caller stored it (ADXF_AddPartition -> ADXERR_CallErrFunc: the original
                              passes its arguments in registers, the callee reads a stack word neither side set)
                    extra     a caller's file that declares more than the definition takes (whole(int, int) for whole(int a4)), or no
                              prototype at all (noproto), is compared on the definition's registers: the rest are leftovers the
                              callee never reads (Virtua Tennis effFootDust -> vecSub(Stk5): r4 a stack pointer in the original, 0 in
                              the C; it was compared on the caller's count, or on every register)
                    key       a function the checker change cannot affect keeps the proof key of the checker saved in
                              state/proof-key-equiv.py, so its earlier pass still counts; one it can affect has a new key
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

CALLER_C = ("int threearg(int);\nvoid fptrs(int, int);\nvoid five(int, int, int, int);\nint whole(int, int);\nextern int noproto();\n"
            "int varproto(int, ...);\nint varused(int, ...);\n\n"
            "int caller(void)\n{\n    five(1, 2, 3, 4);\n    fptrs(1, 2);\n    whole(1, 2);\n    noproto(1, 2, 3, 4);\n"
            "    varproto(1, 2);\n    varused(1, 2);\n    return threearg(1);\n}\n")
DEFS_C = ("int threearg(int a4, int a5, int a6)\n{\n    return a4 + a5 + a6;\n}\n\n"
          "void fptrs(float *vd, float *vs)\n{\n    *vd = *vs;\n}\n\n"
          "void five(int a4, int a5, int a6, int a7, int a8)\n{\n    *(int *)a4 = a8;\n}\n\n"
          "int whole(int a4)\n{\n    return a4;\n}\n\n"
          "int noproto(int a4, int a5, int a6, int a7, int a8, int a9)\n{\n    return a8 + a9;\n}\n\n"
          "int varproto(int a4, int a5, int a6, int a7, int a8)\n{\n    return a8;\n}\n\n"
          "int varused(int a4, int a5, int a6, int a7, int a8)\n{\n    return a4 + a5 + a6 + a7 + a8;\n}\n")
FUNCS = ['threearg', 'fptrs', 'five', 'whole', 'noproto', 'varproto', 'varused', 'caller']


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        os.makedirs(os.path.join(tmp, "src"))
        open(os.path.join(tmp, "src", "caller.c"), "w").write(CALLER_C)
        open(os.path.join(tmp, "src", "defs.c"), "w").write(DEFS_C)
        open(os.path.join(tmp, "functions.txt"), "w").write(
            "".join("F %08x 4 %s\n" % (0x0C010000 + 4 * i, n) for i, n in enumerate(FUNCS)))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "table = equiv.names()\n"
                  "arity, stackn = equiv.compared_arity('src/caller.c', table)\n"
                  "for n in %r:\n"
                  "    print(n, arity.get(table[n]), stackn.get(table[n], 0))\n" % FUNCS[:-1])
        out = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = dict(l.split(' ', 1) for l in out.strip().split('\n') if ' ' in l)
        want = {'threearg': '(3, 0) 0', 'fptrs': '(2, 0) 0', 'five': '(4, 0) 1', 'whole': '(1, 0) 0',
                'noproto': '(4, 0) 2', 'varproto': '(0, 0) 1', 'varused': '(4, 0) 1'}
        bad = ['%s: compared on %s, want %s' % (n, got.get(n, 'nothing'), w) for n, w in want.items() if got.get(n) != w]
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "orig = equiv.callview('0C010100', ['00000001', '00000002', 'AAAA', 'BBBB'], [], {}, None, [True, True, False, False], 1)\n"
                  "drop = equiv.callview('0C010100', ['00000001', 'CCCC', 'AAAA', 'BBBB'], [], {}, None, [True, False, False, False], 1)\n"
                  "keep = equiv.callview('0C010100', ['00000001', '00000002', 'AAAA', 'BBBB'], [], {}, None, [True, True, False, False], 1)\n"
                  "print('dropped', orig == drop)\nprint('kept', orig == keep)\n")
        out2 = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True).stdout
        got2 = dict(l.split(' ', 1) for l in out2.strip().split('\n') if ' ' in l)
        if got2.get('dropped') != 'False':
            bad.append('pointer: a call that sets r4 and r5 equals one that sets only r4 (%s)' % out2.strip()[-200:])
        script = ("import sys, os; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "os.makedirs('state', exist_ok=True); open('case.json', 'w').write('[]')\n"
                  "k = lambda **kw: equiv.proof_key(b'code', 0, 'case.json', {}, b'orig', ('c',), **kw)\n"
                  "plain, aff0 = k(), k(unaffected=True)\n"
                  "open(equiv.PROOF_KEY_LEGACY, 'w').write('old checker')\n"
                  "legacy, aff1 = k(unaffected=True), k()\n"
                  "open(equiv.PROOF_KEY_LEGACY, 'w').write('old checker, edited')\n"
                  "print('nolegacy', plain == aff0)\nprint('affected', aff1 == plain)\nprint('legacy', legacy != plain)\n"
                  "print('follows', k(unaffected=True) != legacy)\n")
        out3 = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True).stdout
        got3 = dict(l.split(' ', 1) for l in out3.strip().split('\n') if ' ' in l)
        for k_, want_ in (('nolegacy', 'True'), ('affected', 'True'), ('legacy', 'True'), ('follows', 'True')):
            if got3.get(k_) != want_:
                bad.append('proof key (%s): %s' % (k_, out3.strip()[-200:]))
        open(os.path.join(tmp, "functions.txt"), "w").write(
            "".join("F %08x 4 %s\n" % (0x8C010000 + 4 * i, n) for i, n in enumerate(FUNCS)))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "table = equiv.names()\n"
                  "arity, stackn = equiv.compared_arity('src/caller.c', table)\n"
                  "equiv.STACKN.clear(); equiv.STACKN.update(stackn)\n"
                  "regs = ['00000000', '00000004', '00000001', '00000000']\n"
                  "view = lambda n, k=None: equiv.callview('%08X' % (0x0C000000 | (table[n] & 0x1FFFFFFF)), regs, [], arity, None, [True] * 4, None, None, None, ['A', 'B', 'C', 'D'])\n"
                  "print('threearg', len(view('threearg')[1]))\n"
                  "print('five', len(view('five')[1]))\n")
        out4 = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True).stdout
        got4 = dict(l.split(' ', 1) for l in out4.strip().split('\n') if ' ' in l)
        for n_, want_ in (('threearg', '3'), ('five', '5')):
            if got4.get(n_) != want_:
                bad.append('mirror: a call to %s linked at 8C... is compared on %s values, want %s (%s)' % (n_, got4.get(n_), want_, out4.strip()[-200:]))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "equiv.STACKN.clear(); equiv.STACKN[0x0C010100] = 1\n"
                  "ar = {0x0C010100: (1, 0)}\n"
                  "v = lambda w, chg: equiv.callview('0C010100', ['00000001', 'X', 'X', 'X'], [], ar, None, [True, False, False, False], None, None, None, [w, 'A', 'B', 'C'], chg)\n"
                  "print('leftover', v('11111111', [False] * 4) == v('22222222', [False] * 4))\n"
                  "print('written', v('11111111', [True] + [False] * 3) == v('22222222', [True] + [False] * 3))\n"
                  "print('unknown', v('11111111', None) == v('22222222', None))\n")
        out5 = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              universal_newlines=True).stdout
        got5 = dict(l.split(' ', 1) for l in out5.strip().split('\n') if ' ' in l)
        for k_, want_ in (('leftover', 'True'), ('written', 'False'), ('unknown', 'False')):
            if got5.get(k_) != want_:
                bad.append('leftover (%s): %s' % (k_, out5.strip()[-300:]))
        if got2.get('kept') != 'True':
            bad.append('pointer: identical pointer calls differ (%s)' % out2.strip()[-200:])
        if not bad:
            print("[equiv] ok: a call is compared on every argument its callee's definition takes (registers and stack), a float "
                  "pointer is an integer argument, a call through a pointer keeps every argument register set, proof keys keep earlier passes of unaffected functions, and registers past the definition's are leftovers, not compared")
            return
        sys.exit("[ERROR] equiv check failed:\n" + "\n".join(bad) + "\n--- output ---\n" + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
