#!/usr/bin/env python3
"""The budget on the generator's tries at writing a node once (scripts/tools/5-generated/gen_equiv/gen_core.py: share_join1,
share_spent). No game data, no compiler. Stdlib only.

Without sharing, a function whose paths multiply reaches its emit limit and is written flat. With it the nodes written once keep the
text under the limit while the paths still multiply, each try snapshots the whole reading, and the reading does not end: Power
Stone 2 FUN_0c0bc420 stopped after 154 s without sharing (13,009 statements, then the flat form) and ran over 11 minutes with it. The
statements a reading writes are counted whether kept or thrown away; once they pass the function's emit limit no further try is made
in that reading and the branches are written the old way.

    check.py      spent     share_spent(written, limit): false up to the limit, true past it; GEN_SHARE_WORK replaces the limit
                  wired     share_join1 asks share_spent before a try, emit counts every statement, a new reading starts at 0
                  bloat     the function's emit limit reached inside a try is not a failed try: it ends the reading (each enclosing try
                            caught it and read its branch again up to the same limit)
                  snapshot  the liveness table (never changed after it is computed) is not copied with each snapshot
"""
import unittest
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CORE = os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_core.py')


class TestGenShareBudget(unittest.TestCase):
    def test_spent(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            with open(os.path.join(tmp, '1ST_READ.BIN'), 'wb') as f:
                f.write(b'\x0b\x00\x09\x00')
            with open(os.path.join(tmp, 'BASE'), 'w') as f:
                f.write('0C010000\n')
            with open(os.path.join(tmp, 'functions.txt'), 'w') as f:
                f.write('F 0c010000 4 fa\n')
            os.makedirs(os.path.join(tmp, 'src'))
            script = ("import os, sys; sys.path.insert(0, 'tools'); import toolpath, gen_core\n"
                      "os.environ.pop('GEN_SHARE_WORK', None)\n"
                      "a = [gen_core.share_spent(w, 100) for w in (0, 100, 101)]\n"
                      "os.environ['GEN_SHARE_WORK'] = '10'\n"
                      "b = [gen_core.share_spent(w, 100) for w in (10, 11)]\n"
                      "print(a, b)\n")
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True).stdout
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(out.strip(), '[False, False, True] [False, True]', out)

    def test_wired(self):
        with open(CORE) as f:
            src = f.read()
        self.assertIn("if share_spent(_SHARE[3],c.emit_limit):", src)
        self.assertIn("c.nemit+=1; _SHARE[3]+=1", src)
        self.assertIn("_SHARE[2]=0; _SHARE[3]=0", src)
        self.assertIn("if isinstance(e,Skip) and str(e).startswith('bloat'): raise", src)

    def test_snapshot(self):
        with open(CORE) as f:
            src = f.read()
        self.assertIn("if k not in ('blocks','stmts','sr_marks','live')}", src)
        self.assertIn("d=copy.deepcopy(d); d['live']=c.__dict__.get('live')", src)


if __name__ == '__main__':
    unittest.main()
