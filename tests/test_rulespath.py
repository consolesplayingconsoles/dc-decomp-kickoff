#!/usr/bin/env python3
"""Where model_map reads models.txt from when no path is given (scripts/tools/3-assets/model_map.py rules_path). No game data. Stdlib only.

    The default went one folder too short after the tools moved into step folders (tools/3-assets): it looked for tools/models.txt, which no
    repo has, so a run of `setup.sh` (which gives no path) read no rules and built a map with none of the repo's tables, characters or textures.
    The repo's models.txt is beside its KICKOFF, one level above tools/.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CALL = "import sys; sys.path.insert(0, '%s'); import model_map; print(model_map.rules_path())"


def rules_path(root, folder):
    out = subprocess.run([sys.executable, "-c", CALL % folder], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True).stdout.strip()
    return out.splitlines()[-1] if out else ""


class TestRulesPath(unittest.TestCase):
    def test_repo_default_is_the_models_txt_beside_kickoff(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"), ignore=shutil.ignore_patterns("__pycache__"))
        got = rules_path(tmp, os.path.join(tmp, "tools", "3-assets"))
        self.assertEqual(os.path.realpath(got), os.path.realpath(os.path.join(tmp, "models.txt")),
                         "a repo's rules are tmp/models.txt, not tmp/tools/models.txt")


if __name__ == "__main__":
    unittest.main()
