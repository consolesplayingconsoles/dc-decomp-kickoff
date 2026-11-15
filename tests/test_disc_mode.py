#!/usr/bin/env python3
"""`make disc` builds the way status.txt's MODE says (scripts/tools/8-build/disc.py, template/Makefile). Sonic Adventure, a matching
repo, had the same `make disc` as the others: the movable build from C, which does not place its matching units, where its build is
build.sh and the overlays. No game data, no compiler: build.sh, build_overlays.sh, the Makefile's `c` and disc_patch.py are stand-ins
that write down that they ran. Stdlib and make.

    check.py      a temp repo with the skill's tools, the template's Makefile (its `c` target replaced by a stand-in) and a stand-in disc:
                    none        no MODE line: `make c`, then the disc takes build/mbuild/game.bin (the repos from before the line)
                    nofile      no status.txt: the same
                    equivalent  MODE: equivalent: the same; build.sh is not run
                    matching    MODE: matching: build.sh, then the disc takes build/out.bin; `make c` is not run
                    overlays    MODE: matching with overlays/<name>/objects.txt and build_overlays.sh: build.sh, the overlays, the disc
                    differs     MODE: matching and build.sh fails: exit 1, the overlays not run, no disc written
                    unknown     MODE: fast: exit 1 with a message naming the word, nothing run
                    plan        --plan prints the mode and its steps and runs nothing
                    makefile    the template's `disc` target runs tools/8-build/disc.py with the GDI (run through make in every case above)
"""
import unittest
from unittest import mock
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

STATUS = "# The decomp's status\n%s[x] BUILDS FROM C\n[ ] BOOTS TO MENU\n"
C_STANDIN = "c:\n\t@echo c >> ran.txt; mkdir -p build/mbuild; echo game > build/mbuild/game.bin\n"
BUILD_SH = "echo match >> ran.txt\n[ -f FAIL ] && { echo DIFFERS; exit 1; }\nmkdir -p build; echo out > build/out.bin; echo MATCH\n"
OVERLAYS_SH = "echo overlays >> ran.txt\n"
PATCH = "import sys\nopen('ran.txt', 'a').write('disc ' + ' '.join(sys.argv[2:]) + '\\n')\n"


def repo(tmp, name, status, overlays=False, fail=False):
    r = os.path.join(tmp, name)
    shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(r, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
    open(os.path.join(r, 'tools', '8-build', 'disc_patch.py'), 'w').write(PATCH)
    mk = open(os.path.join(SKILL, 'template', 'Makefile')).read()
    mk = re.sub(r'(?m)^c:\n(?:\t.*\n)+', C_STANDIN, mk)
    assert 'retcheck' not in mk, 'the stand-in did not replace the template c target'
    open(os.path.join(r, 'Makefile'), 'w').write(mk)
    open(os.path.join(r, 'build.sh'), 'w').write(BUILD_SH)
    if status is not None:
        open(os.path.join(r, 'status.txt'), 'w').write(STATUS % status)
    if overlays:
        os.makedirs(os.path.join(r, 'overlays', 'ADV00'))
        open(os.path.join(r, 'overlays', 'ADV00', 'objects.txt'), 'w').write('a.src\n')
        open(os.path.join(r, 'build_overlays.sh'), 'w').write(OVERLAYS_SH)
    if fail:
        open(os.path.join(r, 'FAIL'), 'w').close()
    open(os.path.join(r, 'game.gdi'), 'w').write('3\n')
    return r


def make_disc(r):
    p = subprocess.run(['make', 'disc', 'GDI=game.gdi'], cwd=r, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=120)
    ran = open(os.path.join(r, 'ran.txt')).read().split('\n')[:-1] if os.path.exists(os.path.join(r, 'ran.txt')) else []
    return p.returncode, ran, p.stdout


class TestDiscMode(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_disc_mode(self):
        tmp = tempfile.mkdtemp(prefix='disc_mode_')
        try:
            assert 'tools/8-build/disc.py "$(GDI)"' in open(os.path.join(SKILL, 'template', 'Makefile')).read(), 'the template disc target does not run disc.py'
            eq = ['c', 'disc build/disc-cbuild 1ST_READ.BIN=build/mbuild/game.bin']
            for name, status in (('none', ''), ('nofile', None), ('equivalent', 'MODE: equivalent\n')):
                rc, ran, out = make_disc(repo(tmp, name, status))
                assert rc == 0 and ran == eq, '%s: an equivalent repo does not run make c and take its executable: %s\n%s' % (name, ran, out)
                assert 'MODE equivalent' in out, '%s: the mode is not said:\n%s' % (name, out)
            rc, ran, out = make_disc(repo(tmp, 'matching', 'MODE: matching\n'))
            assert rc == 0 and ran == ['match', 'disc build/disc-cbuild 1ST_READ.BIN=build/out.bin'], 'matching: not build.sh and its executable: %s\n%s' % (ran, out)
            assert 'MODE matching' in out, 'matching: the mode is not said:\n' + out
            rc, ran, out = make_disc(repo(tmp, 'overlays', 'MODE: matching\n', overlays=True))
            assert rc == 0 and ran == ['match', 'overlays', 'disc build/disc-cbuild 1ST_READ.BIN=build/out.bin'], 'overlays: not build.sh, the overlays, the disc: %s\n%s' % (ran, out)
            rc, ran, out = make_disc(repo(tmp, 'differs', 'MODE: matching\n', overlays=True, fail=True))
            assert rc != 0 and ran == ['match'] and 'no disc written' in out, 'differs: a build that does not match goes on: %s\n%s' % (ran, out)
            rc, ran, out = make_disc(repo(tmp, 'unknown', 'MODE: fast\n'))
            assert rc != 0 and ran == [] and 'MODE: fast' in out, 'unknown: an unknown mode is not refused before anything runs: %s\n%s' % (ran, out)
            r = repo(tmp, 'plan', 'MODE: matching\n', overlays=True)
            p = subprocess.run([sys.executable, 'tools/8-build/disc.py', '--plan'], cwd=r, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            assert p.returncode == 0 and 'MODE matching' in p.stdout and 'build_overlays.sh' in p.stdout and not os.path.exists(os.path.join(r, 'ran.txt')), \
                'plan: --plan does not print the steps, or runs one:\n' + p.stdout
            print('[disc_mode] ok: make disc runs make c for an equivalent repo (also with no MODE line) and build.sh with the overlays for a matching one; a build that differs or an unknown mode writes no disc')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
