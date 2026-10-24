#!/usr/bin/env python3
"""gen_equiv in a repo with no C yet (scripts/tools/5-generated/gen_equiv). A first run has no tests/equivalent.txt: the generator can work
with an empty one, so it creates it; it must not die on the missing file (Zombie Revenge, 2026-10-24: FileNotFoundError, no run).
No game data, no compiler: a temp repo with an empty function list. Stdlib only.

    check.py      a temp repo with functions.txt, BASE, 1ST_READ.BIN, sdk-verified.txt and no tests/:
                    the run does not fail on tests/equivalent.txt
                    tests/equivalent.txt exists afterwards, empty
                    a second run leaves a file with content as it was
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv')


def run(repo):
    return subprocess.run([sys.executable, TOOL, '--run', 'fresh', '--jobs', '1'], cwd=repo, capture_output=True, text=True, timeout=120)


def main():
    repo = tempfile.mkdtemp(prefix='gen_equiv_fresh_')
    try:
        for name, text in (('functions.txt', ''), ('BASE', '0C010000\n'), ('sdk-verified.txt', '# none\n')):
            open(os.path.join(repo, name), 'w').write(text)
        open(os.path.join(repo, '1ST_READ.BIN'), 'wb').write(b'\0' * 64)
        r = run(repo)
        out = r.stdout + r.stderr
        eq = os.path.join(repo, 'tests', 'equivalent.txt')
        assert 'equivalent.txt' not in out, 'the run fails on the missing tests/equivalent.txt:\n' + out[-600:]
        assert os.path.exists(eq), 'tests/equivalent.txt is not created'
        assert open(eq).read() == '', 'tests/equivalent.txt is not empty'
        open(eq, 'w').write('keep_me\n')
        run(repo)
        assert open(eq).read() == 'keep_me\n', 'a second run changed the file'
        print('[gen_equiv_fresh] ok: a repo with no tests/ gets an empty tests/equivalent.txt, a filled one is left alone')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


main()
