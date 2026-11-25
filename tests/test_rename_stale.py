#!/usr/bin/env python3
"""rename.py --stale (scripts/tools/common/rename.py): put the current name where a function's placeholder is still used. No game data,
no compiler. Stdlib only.

Every function starts as FUN_<address>. Naming it later in functions.txt (by hand, from a sibling decomp) leaves the C that already
exists calling the placeholder; the asm piece carries the new name as its label, so a build from the C links nothing for `FUN_<address>`
(Power Stone 2: 47 functions, 1,300 uses in 302 files; the proofs passed, since they find a function by its address).
`--stale` is the rename of those placeholders to the names functions.txt gives them: whole words in the repo's text files, a C definition
under the placeholder too, and its case file tests/<file>/FUN_<address>.json moves to the new name. functions.txt does not change.

    check.py      dry run     counts, changes nothing
                  apply       calls and a definition use the new name; the case file moves; a function still called FUN_<address> is left;
                              a name that merely contains a placeholder is left (whole words)
                  both        a placeholder and its new name both defined in C: refused, nothing changes
                  none        nothing stale in the C: no file changes
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)


def repo(files, functions):
    tmp = tempfile.mkdtemp(prefix='rename_stale_')
    shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
    files = dict(files, **{'functions.txt': functions})
    for p, t in files.items():
        os.makedirs(os.path.dirname(os.path.join(tmp, p)) or tmp, exist_ok=True)
        with open(os.path.join(tmp, p), 'w') as fh:
            fh.write(t)
    subprocess.run(['git', 'init', '-q'], cwd=tmp, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=tmp, check=True)
    return tmp


def run(tmp, *args):
    return subprocess.run([sys.executable, 'tools/common/rename.py'] + list(args), cwd=tmp, capture_output=True, text=True, timeout=60)


def read(tmp, p):
    with open(os.path.join(tmp, p)) as fh:
        return fh.read()


FUNCS = 'F 0c010000 8 FUN_0c010000\nF 0c010010 8 nlLocate\nF 0c010020 8 strlen\n'
A_C = 'int nlLocate(int x);\nint a(void) { return FUN_0c010010(1) + nlLocate(2) + FUN_0c010000(3) + FUN_0c010010_x; }\n'
B_C = 'int FUN_0c010020(int a4)\n{\n    return a4;\n}\n'


class TestRenameStale(unittest.TestCase):
    def setUp(self):
        self.tmp = repo({'src/a.c': A_C, 'src/b.c': B_C, 'tests/b/FUN_0c010020.json': '{}', 'docs/n.md': 'FUN_0c010010 is called here\n'}, FUNCS)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_dry_run(self):
        r = run(self.tmp, '--stale')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('renames: 2', r.stdout)
        self.assertEqual(read(self.tmp, 'src/a.c'), A_C)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'tests/b/FUN_0c010020.json')))

    def test_apply(self):
        r = run(self.tmp, '--stale', '--apply')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a = read(self.tmp, 'src/a.c')
        self.assertIn('nlLocate(1) + nlLocate(2) + FUN_0c010000(3)', a)
        self.assertIn('FUN_0c010010_x', a)                       # whole words only
        self.assertIn('int strlen(int a4)', read(self.tmp, 'src/b.c'))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'tests/b/strlen.json')))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, 'tests/b/FUN_0c010020.json')))
        self.assertIn('nlLocate is called here', read(self.tmp, 'docs/n.md'))
        self.assertEqual(read(self.tmp, 'functions.txt'), FUNCS)

    def test_both(self):
        tmp = repo({'src/a.c': 'int FUN_0c010010(void)\n{\n    return 1;\n}\n', 'src/b.c': 'int nlLocate(void)\n{\n    return 2;\n}\n'}, FUNCS)
        self.addCleanup(shutil.rmtree, tmp, True)
        r = run(tmp, '--stale', '--apply')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('both defined', r.stdout + r.stderr)
        self.assertIn('FUN_0c010010', read(tmp, 'src/a.c'))

    def test_none(self):
        tmp = repo({'src/a.c': 'int a(void) { return nlLocate(1); }\n'}, FUNCS)
        self.addCleanup(shutil.rmtree, tmp, True)
        r = run(tmp, '--stale', '--apply')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('renames: 2', r.stdout)                    # the two named functions are candidates; only uses count
        self.assertIn('files changed: 0', r.stdout)


if __name__ == '__main__':
    unittest.main()
