#!/usr/bin/env python3
"""The version a map states (scripts/tools/3-assets/model_map.py skill_version). No game data. Stdlib only.

    check.py      the tool from the step folder (tools/3-assets) of a repo reads the repo's KICKOFF (one level above tools/); the same
                  tool in the skill (scripts/tools/3-assets) reads the skill's VERSION (two levels above scripts/): the lookup once
                  went one folder too short after the tools moved into step folders, so every repo's map tool refused to run
                  ("no version: .../tools has no KICKOFF"), Zombie Revenge, 2026-10-26.
"""
import unittest
from unittest import mock
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CALL = "import sys; sys.path.insert(0, '%s'); import model_map; print(model_map.skill_version())"


def version(root, folder):
    out = subprocess.run([sys.executable, "-c", CALL % folder], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True).stdout.strip()
    return out.splitlines()[-1] if out else ""


class TestMapversion(unittest.TestCase):
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

    def test_mapversion(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"), ignore=shutil.ignore_patterns("__pycache__"))
            for stamp in ("unstable", "v1.0+77b3ada"):
                open(os.path.join(tmp, "KICKOFF"), "w").write(stamp + "\n")
                got = version(tmp, os.path.join(tmp, "tools", "3-assets"))
                if got != stamp:
                    bad.append("repo: KICKOFF %r read as %r" % (stamp, got))
            got = version(SKILL, os.path.join(SKILL, "scripts", "tools", "3-assets"))
            want = open(os.path.join(SKILL, "VERSION")).read().strip()
            if got != want:
                bad.append("skill: VERSION %r read as %r" % (want, got))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail("[ERROR] mapversion check failed:\n" + "\n".join(bad))


if __name__ == '__main__':
    unittest.main()
