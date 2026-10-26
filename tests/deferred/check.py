#!/usr/bin/env python3
"""Step 5's batch check checks every function it is given (scripts/tools/5-generated/gen_equiv/gen_pipe.py run_file_robust), with no
game data and no compiler: the generator modules and the checker are stand-ins. Stdlib only.

    check.py      a batch where two functions declare the same callee with different prototypes:
                    deferred  the second could not share the first's scratch file and was handed back as "deferred", which no caller
                              checked or recorded: no C, no result row (Virtua Tennis --regen: 13 of 92 functions drawn were never
                              checked, and got their old C back). Each one must come back passed or failed
                    verdicts  a deferred function that differs is failed, not passed
                    groups    the passed functions are written in groups whose prototypes agree, one file each: written together, a
                              head declaring the callee one way broke the file for the function proven against the other (Virtua Tennis
                              gen_ek.c: motionRootFirst against the old vecMake, 15 proven functions in a file that did not compile)
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
