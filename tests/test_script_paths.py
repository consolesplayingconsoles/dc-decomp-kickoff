#!/usr/bin/env python3
"""Every path a shell script builds from its own folder ("$HERE/...") exists in the skill.

A script that sources or runs a file beside it ("$HERE/docker_check.sh", "$HERE/tools-image") breaks the moment that file
moves to another folder and the script is not updated: the step fails on its first line with "No such file". This reads
every .sh under scripts/ for the folder it calls HERE and checks each "$HERE/<path>" it names.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), 'scripts')


def here_paths(text):
    """The relative paths a script names as "$HERE/<path>" (shell variables in the path end it)."""
    out = []
    for m in re.finditer(r'"?\$HERE/([A-Za-z0-9_./\-]+)', text):
        p = m.group(1).rstrip('./')
        if p and '$' not in p:
            out.append(p)
    return out


class HerePathsTest(unittest.TestCase):
    def test_the_reader_finds_sourced_and_run_paths(self):
        text = '. "$HERE/docker_check.sh"\npython3 "$HERE/iso_extract.py" "$SRC"\ndocker_ready "$HERE/tools-image"\n'
        self.assertEqual(here_paths(text), ['docker_check.sh', 'iso_extract.py', 'tools-image'])

    def test_every_here_path_in_every_shell_script_exists(self):
        missing = []
        for root, _, files in os.walk(SCRIPTS):
            if '__pycache__' in root:
                continue
            for f in files:
                if not f.endswith('.sh'):
                    continue
                path = os.path.join(root, f)
                with open(path, errors='replace') as fh:
                    text = fh.read()
                if not re.search(r'^\s*HERE=.*dirname.*\$0', text, re.M):
                    continue
                for rel in here_paths(text):
                    if not os.path.exists(os.path.normpath(os.path.join(root, rel))):
                        missing.append('%s: $HERE/%s' % (os.path.relpath(path, SCRIPTS), rel))
        self.assertEqual(missing, [], 'paths a script builds from its own folder that do not exist')


if __name__ == '__main__':
    unittest.main()
