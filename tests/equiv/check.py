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

CALLER_C = ("int threearg(int);\nvoid fptrs(int, int);\nvoid five(int, int, int, int);\nint whole(int, int);\n\n"
            "int caller(void)\n{\n    five(1, 2, 3, 4);\n    fptrs(1, 2);\n    whole(1, 2);\n    return threearg(1);\n}\n")
DEFS_C = ("int threearg(int a4, int a5, int a6)\n{\n    return a4 + a5 + a6;\n}\n\n"
          "void fptrs(float *vd, float *vs)\n{\n    *vd = *vs;\n}\n\n"
          "void five(int a4, int a5, int a6, int a7, int a8)\n{\n    *(int *)a4 = a8;\n}\n\n"
          "int whole(int a4)\n{\n    return a4;\n}\n")
FUNCS = ['threearg', 'fptrs', 'five', 'whole', 'caller']


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
                  "    print(n, arity.get(table[n]), stackn.get(table[n], 0))\n" % FUNCS[:4])
        out = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = dict(l.split(' ', 1) for l in out.strip().split('\n') if ' ' in l)
        want = {'threearg': '(3, 0) 0', 'fptrs': '(2, 0) 0', 'five': '(4, 0) 1', 'whole': '(2, 0) 0'}
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
        if got2.get('kept') != 'True':
            bad.append('pointer: identical pointer calls differ (%s)' % out2.strip()[-200:])
        if not bad:
            print("[equiv] ok: a call is compared on every argument its callee's definition takes (registers and stack), a float "
                  "pointer is an integer argument, a call through a pointer keeps every argument register set, proof keys keep earlier passes of unaffected functions, and a prototype naming more than the definition keeps its own count")
            return
        sys.exit("[ERROR] equiv check failed:\n" + "\n".join(bad) + "\n--- output ---\n" + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
