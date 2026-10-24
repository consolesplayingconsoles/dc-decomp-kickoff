#!/usr/bin/env python3
"""consistency.py --fix tells what it is doing while it does it (scripts/tools/consistency.py). A repair re-checks whole files with
tools/equiv.py and can take many minutes; the log stayed empty until the end (Virtua Tennis, 2026-10-24: "there is no log output yet").
No game data, no compiler: a stub tools/equiv.py that sleeps. Stdlib only.

    check.py      a temp repo with one generated function that has C and cases but no recorded pass, and a stub equiv.py that takes 4 s:
                    the first line (`checking src/gen_a.c`) arrives within 2.5 s, while --fix is still running
                    every repair line is printed as it is made, flushed (the output is a pipe, as in a log file)
"""
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'consistency.py')


def main():
    repo = tempfile.mkdtemp(prefix='consistency_progress_')
    try:
        for d in ('src', 'state', 'tools', 'tests/gen_a'):
            os.makedirs(os.path.join(repo, d))
        open(os.path.join(repo, 'functions.txt'), 'w').write('F 8c010000 32 f_a\n')
        open(os.path.join(repo, 'src', 'gen_a.c'), 'w').write('int f_a(int a4)\n{\n    return a4;\n}\n')
        open(os.path.join(repo, 'tests', 'gen_a', 'f_a.json'), 'w').write('{}')
        open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write('')
        open(os.path.join(repo, 'tools', 'equiv.py'), 'w').write('import time\ntime.sleep(4)\n')
        t0 = time.time()
        p = subprocess.Popen([sys.executable, TOOL, '--fix'], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ready = select.select([p.stdout], [], [], 2.5)[0]
        first = p.stdout.readline() if ready else ''
        alive = p.poll() is None
        rest = p.communicate(timeout=60)[0]
        assert ready and 'checking src/gen_a.c' in first, 'no progress line within 2.5 s (got %r)' % first
        assert alive, 'the line came only when --fix had finished (%.1f s)' % (time.time() - t0)
        assert 'f_a: does not pass in src/gen_a.c' in rest, 'the repair line is missing:\n' + rest
        print('[consistency_progress] ok: --fix names the file it is checking before it checks, and each repair as it is made')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


main()
