#!/usr/bin/env python3
"""The scratch a run leaves in src/ and tests/ is taken away (scripts/tools/5-generated/gen_equiv/scratch.py). No game data, no compiler.
Stdlib only.

A function defined in a scratch file (src/gen_tmp<round>p<pid>[c|v].c) counts as defined: the next run does not pick it and the build's
checks read its C. The files carry the process id of the run that wrote them, and the run removed only `gen_tmp*p<pid>.c`, which does not
match the files with a letter after the id: every run left them, and a stopped one left everything.

    check.py      a temp repo with scratch of a process that is gone, of this one and of one still running:
                    sweep     the files and directories of the gone process go (c and v ones, tests dirs, a recheck's gen_tmpK)
                    alive     those of this process, and of another one still running, stay
                    other     src/gen_x.c, the batch files, stay
                    own       remove_own takes this process's, c and v ones too, and not another process whose id starts with ours
                    nested    a gone process's scratch in a folder of src/ (src/game/) goes too
                    tracked   a gone process's scratch that git tracks (it was committed) stays
"""
import unittest
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv'))
import scratch  # noqa: E402


class TestScratch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.src = os.path.join(self.tmp, 'src')
        self.tests = os.path.join(self.tmp, 'tests')
        os.makedirs(self.src)
        os.makedirs(self.tests)
        p = subprocess.Popen([sys.executable, '-c', 'pass'])
        p.wait()
        self.gone = p.pid
        self.sleeper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(self.sleeper.kill)
        self.me = os.getpid()

    def make(self, pid, rnd=0, letters=('c', 'v')):
        for ch in letters:
            open(os.path.join(self.src, 'gen_tmp%dp%d%s.c' % (rnd, pid, ch)), 'w').write('int f(void){return 0;}\n')
            os.makedirs(os.path.join(self.tests, 'gen_tmp%dp%d%s' % (rnd, pid, ch)))
        open(os.path.join(self.src, 'gen_tmpK%d.c' % pid), 'w').write('int g(void){return 0;}\n')
        os.makedirs(os.path.join(self.tests, 'gen_tmpK%d' % pid))

    def names(self):
        return sorted(os.listdir(self.src) + os.listdir(self.tests))

    def test_scratch(self):
        bad = []
        self.make(self.gone)
        self.make(self.me)
        self.make(self.sleeper.pid)
        open(os.path.join(self.src, 'gen_x.c'), 'w').write('int h(void){return 0;}\n')
        scratch.sweep(self.src, self.tests)
        left = self.names()
        if any(str(self.gone) in n for n in left):
            bad.append('sweep: the scratch of a process that is gone is still there: %r' % [n for n in left if str(self.gone) in n])
        for pid, what in ((self.me, 'this process'), (self.sleeper.pid, 'a running process')):
            if not any('p%d' % pid in n for n in left):
                bad.append('alive: the scratch of %s was removed' % what)
        if 'gen_x.c' not in left:
            bad.append('other: src/gen_x.c was removed')
        longer = int('%d9' % self.me)
        self.make(longer, letters=('c',))
        scratch.remove_own(self.src, self.tests)
        left = self.names()
        if any(n.startswith('gen_tmp') and ('p%dc' % self.me in n or 'p%dv' % self.me in n or n == 'gen_tmpK%d.c' % self.me) for n in left):
            bad.append('own: this process\'s scratch is still there: %r' % [n for n in left if str(self.me) in n])
        if not any('p%d' % longer in n for n in left):
            bad.append('own: the scratch of process %d went with ours (%d)' % (longer, self.me))
        os.makedirs(os.path.join(self.src, 'game'))
        nested = os.path.join(self.src, 'game', 'gen_tmp0p%dv.c' % self.gone)
        committed = os.path.join(self.src, 'game', 'gen_tmp1p%dv.c' % self.gone)
        for f in (nested, committed):
            open(f, 'w').write('int f(void){return 0;}\n')
        git = lambda *a: subprocess.run(['git'] + list(a), cwd=self.tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        git('init', '-q')
        git('add', os.path.relpath(committed, self.tmp))
        cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            scratch.sweep('src', 'tests')
        finally:
            os.chdir(cwd)
        if os.path.exists(nested):
            bad.append('nested: the scratch of a gone process in src/game/ is still there')
        if not os.path.exists(committed):
            bad.append('tracked: a scratch file git tracks was removed')
        if bad:
            self.fail('[ERROR] scratch check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
