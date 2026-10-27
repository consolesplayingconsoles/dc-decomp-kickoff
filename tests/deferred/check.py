#!/usr/bin/env python3
"""Step 5's batch check checks every function it is given (scripts/tools/5-generated/gen_equiv/gen_pipe.py run_file_robust), with no
game data and no compiler: the generator modules and the checker are stand-ins. Stdlib only.

    check.py      a batch where two functions declare the same callee with different prototypes:
                    deferred  the second could not share the first's scratch file and was handed back as "deferred", which no caller
                              checked or recorded: no C, no result row (Virtua Tennis --regen: 13 of 92 functions drawn were never
                              checked, and got their old C back). Each one must come back passed or failed
                    verdicts  a deferred function that differs is failed, not passed
                    definition a function defined in the batch (e(int a4, float f4)) and a caller that declares it otherwise (int e(int))
                              go to separate files: in one, the head declares the definition and the call has too few arguments
                              (Zombie Revenge FUN_0c0de230: "Scalar required" on return FUN_0c0de850(a4))
                    linkfail  a batch that fails as a whole (a link error: one function's C needs a helper the repo does not name) is
                              split until the failing function is found: it is dropped with the error, every other one gets its verdict
                              (Zombie Revenge: 456 functions in 15 batches got no verdict at all, "undefined _quick_evn_mvn")
                    groups    the passed functions are written in groups whose prototypes agree, one file each: written together, a
                              head declaring the callee one way broke the file for the function proven against the other (Virtua Tennis
                              gen_ek.c: motionRootFirst against the old vecMake, 15 proven functions in a file that did not compile)
                    empty     a batch whose only function does not compile is dropped with the error and the batch returns: dropping
                              it left nothing to check and the runner crashed (IndexError on gs[0]; Virtua Tennis and Zombie Revenge
                              --regen: cpuSglHitCheck alone in batch 4, 127 functions never drawn; ZR's last 24 never checked)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
import toolpath  # noqa: E402,F401

drv = types.ModuleType('gen_drv')
drv.head_protos = lambda use: '\n'.join(sorted({v for it in use for v in it[3].values()}))
core = types.ModuleType('gen_core')
core.Skip = type('Skip', (Exception,), {})
sys.modules['gen_drv'] = drv
sys.modules['gen_core'] = core
import gen_pipe  # noqa: E402

DIFFER = set()


def fake_run(cmd, capture_output=True, text=True):
    t = open(cmd[-1]).read()
    if 'int cbad(void)' in t:
        ln = t.split('\n').index('int cbad(void)') + 2
        return types.SimpleNamespace(stdout='compile failed\nsrc/gen_tmp0.c(%d) : Undeclared name "q"\n' % ln, stderr='', returncode=1)
    if 'int linkbad(void)' in t:
        return types.SimpleNamespace(stdout='[ERROR] link: undefined _quick_evn_mvn (name them in functions.txt)\n', stderr='', returncode=1)
    names = re.findall(r'^int (\w+)\(void\)\n\{', t, re.M)
    out = ''.join('%-28s %s\n' % (n, 'DIFFERS     case 1: out' if n in DIFFER else 'EQUIVALENT  1 case') for n in names)
    return types.SimpleNamespace(stdout=out, stderr='', returncode=0)


def item(n, protos):
    return (n, 'int %s(void)\n{\n    return 0;\n}' % n, [{'r4': 0}], protos)


def main():
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    bad = []
    real = subprocess.run
    try:
        os.chdir(tmp)
        os.makedirs('src'); os.makedirs('tests')
        gen_pipe.subprocess.run = fake_run
        items = [item('a', {'x': 'int x(int);'}), item('b', {'x': 'int x(void);'}), item('c', {'y': 'int y(void);'}),
                 item('d', {'x': 'float x(int);'})]
        passed, failed, deferred, dropped, err = gen_pipe.run_file_robust('gen_tmp0', items)
        if sorted(passed) != ['a', 'b', 'c', 'd'] or deferred:
            bad.append('deferred: passed %s, deferred %s; want a, b, c, d passed and nothing deferred' % (sorted(passed), [i[0] for i in deferred]))
        DIFFER.add('b')
        passed, failed, deferred, dropped, err = gen_pipe.run_file_robust('gen_tmp0', items)
        if failed != ['b'] or sorted(passed) != ['a', 'c', 'd']:
            bad.append('verdicts: passed %s failed %s; want b failed, a c d passed' % (sorted(passed), failed))
        e = ('e', 'int e(int a4, float f4)\n{\n    return a4;\n}', [{'r4': 0}], {})
        f = item('f', {'e': ('int',)})
        dg = gen_pipe.compatible_groups([e, f])
        if len(dg) != 2:
            bad.append('definition: %s; want e and its caller f in separate groups' % [[i[0] for i in g] for g in dg])
        DIFFER.clear()
        lk = [item('l%d' % k, {}) for k in range(5)] + [item('linkbad', {})] + [item('m%d' % k, {}) for k in range(4)]
        passed, failed, deferred, dropped, err = gen_pipe.run_file_robust('gen_tmp0', lk)
        if sorted(passed) != sorted(['l%d' % k for k in range(5)] + ['m%d' % k for k in range(4)]) or dropped != ['linkbad']:
            bad.append('linkfail: passed %s dropped %s; want the nine others passed and linkbad dropped' % (sorted(passed), dropped))
        elif 'undefined' not in gen_pipe.LAST.get('why', {}).get('linkbad', ''):
            bad.append('linkfail: linkbad dropped without its error: %r' % gen_pipe.LAST.get('why', {}).get('linkbad'))
        try:
            r = gen_pipe.run_file_robust('gen_tmp0', [item('cbad', {})])
            if r[0] or r[1] or r[2] or r[3] != ['cbad']:
                bad.append('empty: %s; want cbad dropped and nothing else' % (r[:4],))
            elif 'Undeclared' not in gen_pipe.LAST.get('why', {}).get('cbad', ''):
                bad.append('empty: cbad dropped without its error: %r' % gen_pipe.LAST.get('why', {}).get('cbad'))
        except IndexError as e:
            bad.append('empty: the batch crashed once its only function was dropped (IndexError: %s)' % e)
        gs = gen_pipe.compatible_groups(items)
        if sorted(sorted(i[0] for i in g) for g in gs) != [['a', 'c'], ['b'], ['d']]:
            bad.append('groups: %s; want a+c, b, d' % [[i[0] for i in g] for g in gs])
        main_src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', '__main__.py')).read()
        if 'gen_pipe.compatible_groups(keep)' not in main_src:
            bad.append('groups: write_batch does not split the passed functions with gen_pipe.compatible_groups')
        if [f for f in os.listdir('src') if f != 'gen_tmp0.c'] or [d for d in os.listdir('tests') if d != 'gen_tmp0']:
            bad.append('scratch: the deferred rounds left %s %s' % (os.listdir('src'), os.listdir('tests')))
    finally:
        gen_pipe.subprocess.run = real
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit("[ERROR] deferred check failed:\n" + "\n".join(bad))
    print("[deferred] ok: a function whose prototypes clash with its batch is still checked, in a scratch file of its own")


if __name__ == '__main__':
    main()
