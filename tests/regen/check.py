#!/usr/bin/env python3
"""gen_equiv --regen: step 5 writes named functions again when their generated C exists (scripts/tools/5-generated/gen_equiv/regen.py),
with no game data and no compiler. Stdlib only.

    check.py      a temp repo with generated, hand-written and manual-marked C:
                    out       a generated function's C, cases and equivalent.txt line are taken out, so step 5 picks it as a function
                              with no C; hand-written C and C marked manual are never taken out (Virtua Tennis: functions whose generated
                              C differed had no way back through step 5, which skips every function with C)
                    back      a function the run did not prove gets its old C, cases and equivalent.txt line back
                    kept      a function the run proved keeps the new C: the old is not put back, and a file left with no function goes
                    once      putting back twice (the run's end, then its exit) restores once
                    wired     gen_equiv's __main__ takes --regen, takes out before it reads equivalent.txt, and puts back on exit
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
import toolpath  # noqa: E402,F401
import regen  # noqa: E402

F = 'int f(int a4)\n{\n    return a4;\n}\n'
H = '/* manual: kept by hand */\nint h(void)\n{\n    return 1;\n}\n'
G = 'int g(void)\n{\n    return 2;\n}\n'
K = 'int k(void)\n{\n    return 3;\n}\n'


def repo():
    os.makedirs('src'); os.makedirs('tests/gen_a'); os.makedirs('tests/gen_b'); os.makedirs('tests/hand'); os.makedirs('state')
    open('src/gen_a.c', 'w').write('int f(int);\nint k(void);\n\n' + F + '\n' + K)
    open('src/gen_b.c', 'w').write('int h(void);\n\n' + H)
    open('src/hand.c', 'w').write(G)
    for stem, fn in (('gen_a', 'f'), ('gen_a', 'k'), ('gen_b', 'h'), ('hand', 'g')):
        json.dump([{'r4': fn}], open('tests/%s/%s.json' % (stem, fn), 'w'))
    open('tests/equivalent.txt', 'w').write('k\nf\ng\n')


def main():
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    bad = []
    try:
        os.chdir(tmp)
        repo()
        recs, skipped = regen.take_out(['f', 'g', 'h', 'nosuch'])
        if [r['fn'] for r in recs] != ['f']:
            bad.append('out: took out %s, want only f' % [r['fn'] for r in recs])
        if sorted(skipped) != ['g', 'h', 'nosuch']:
            bad.append('out: skipped %s, want g, h, nosuch' % sorted(skipped))
        a = open('src/gen_a.c').read()
        if 'int f(int a4)\n{' in a or K not in a:
            bad.append('out: gen_a.c should lose f and keep k')
        if os.path.exists('tests/gen_a/f.json') or 'f' in open('tests/equivalent.txt').read().split():
            bad.append('out: f\'s cases or equivalent.txt line are still there')
        if open('src/hand.c').read() != G or H not in open('src/gen_b.c').read():
            bad.append('out: hand-written or manual C was touched')
        regen.put_back(recs, set())
        regen.put_back(recs, set())
        a = open('src/gen_a.c').read()
        if a.count('int f(int a4)\n{') != 1:
            bad.append('back/once: f is in gen_a.c %d times, want 1' % a.count('int f(int a4)\n{'))
        if not os.path.exists('tests/gen_a/f.json') or open('tests/equivalent.txt').read().split().count('f') != 1:
            bad.append('back: f\'s cases or equivalent.txt line did not come back')
        shutil.rmtree('src'); shutil.rmtree('tests'); shutil.rmtree('state')
        repo()
        open('src/gen_a.c', 'w').write('int f(int);\n\n' + F)
        os.remove('tests/gen_a/k.json')
        recs, _ = regen.take_out(['f'])
        regen.put_back(recs, {'f'})
        if os.path.exists('src/gen_a.c') or os.path.exists('tests/gen_a'):
            bad.append('kept: gen_a.c, left with no function, should be gone')
        if 'f' in open('tests/equivalent.txt').read().split():
            bad.append('kept: the old equivalent.txt line came back over the new C')
        src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', '__main__.py')).read()
        i_out, i_keep = src.find('regen.take_out('), src.find("KEEP={f:open(f).read()")
        if i_out < 0 or not (0 <= i_out < i_keep):
            bad.append('wired: __main__ does not take out before it snapshots equivalent.txt')
        if 'atexit.register' not in src or "'--regen'" not in src:
            bad.append('wired: __main__ does not take --regen or put back on exit')
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit("[ERROR] regen check failed:\n" + "\n".join(bad))
    print("[regen] ok: generated C is taken out for step 5 and put back unless the new C is proven; hand-written C is never touched")


if __name__ == '__main__':
    main()
