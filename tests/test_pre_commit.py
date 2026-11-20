#!/usr/bin/env python3
"""The repo's pre-commit hook (scripts/tools/hooks/pre-commit), run in a temp git repo with a stand-in tools/progress.py.
No game data, no compiler. Needs git and bash. Stdlib only.

    progress    a commit rewrites the README's Progress block with progress.py's report
    big         a staged file over PRE_COMMIT_MAX_MB refuses the commit and names the file
    small       a staged file under the limit commits
    failing     progress.py failing refuses the commit and shows its error
    unstaged    a proof record changed but not staged (tests/equivalent.txt) stays out of the commit: the hook adds only the
                README's Progress block and the badge it writes itself
"""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', 'hooks', 'pre-commit')

PROGRESS_OK = 'print("FUNCTIONS LEFT 0")\n'
PROGRESS_FAIL = 'import sys\nsys.exit("status.txt: a tick under a cross")\n'


@unittest.skipUnless(shutil.which('git') and shutil.which('bash'), 'needs git and bash')
class PreCommit(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix='pre_commit')
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'test')
        os.makedirs(os.path.join(self.repo, 'tools', 'hooks'))
        shutil.copy(HOOK, os.path.join(self.repo, 'tools', 'hooks', 'pre-commit'))
        os.chmod(os.path.join(self.repo, 'tools', 'hooks', 'pre-commit'), 0o755)
        self.git('config', 'core.hooksPath', 'tools/hooks')
        self.write('README.md', '# Game\n\n<!-- progress -->\n```\nold\n```\n<!-- /progress -->\n')
        self.write('functions.txt', 'F 0c010000 4 main\n')
        self.write('tools/progress.py', PROGRESS_OK)

    def git(self, *args, env=None):
        return subprocess.run(['git'] + list(args), cwd=self.repo, capture_output=True, text=True,
                              env=dict(os.environ, **(env or {})))

    def write(self, rel, text):
        p = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w') as f:
            f.write(text)

    def commit(self, env=None):
        self.git('add', '-A')
        return self.git('commit', '-q', '-m', 'test', env=env)

    def test_progress(self):
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.repo, 'README.md')) as f:
            self.assertIn('FUNCTIONS LEFT 0', f.read(), 'the block holds progress.py\'s report')

    def test_big(self):
        with open(os.path.join(self.repo, 'core'), 'wb') as f:
            f.write(b'\0' * (2 * 1048576 + 1))
        r = self.commit(env={'PRE_COMMIT_MAX_MB': '1'})
        self.assertNotEqual(r.returncode, 0, 'a file over the limit refuses the commit')
        self.assertIn('core (2 MB)', r.stderr)
        self.assertIn('commit refused', r.stderr)

    def test_small(self):
        with open(os.path.join(self.repo, 'data.bin'), 'wb') as f:
            f.write(b'\0' * 1000)
        r = self.commit(env={'PRE_COMMIT_MAX_MB': '1'})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_failing(self):
        self.write('tools/progress.py', PROGRESS_FAIL)
        r = self.commit()
        self.assertNotEqual(r.returncode, 0, 'a failing progress.py refuses the commit')
        self.assertIn('a tick under a cross', r.stderr, 'its error is shown')
        self.assertIn('tools/progress.py failed', r.stderr)

    def test_unstaged(self):
        self.write('tests/equivalent.txt', 'main\n')
        self.write('tools/equiv.py', '')
        self.assertEqual(self.commit().returncode, 0)
        self.write('tests/equivalent.txt', 'main\nother\n')       # changed, not staged
        self.write('notes.txt', 'x')
        self.git('add', 'notes.txt')
        r = self.git('commit', '-q', '-m', 'notes')
        self.assertEqual(r.returncode, 0, r.stderr)
        files = self.git('show', '--name-only', '--format=', 'HEAD').stdout.split()
        self.assertNotIn('tests/equivalent.txt', files, 'a file the user did not stage stays out: %s' % files)


if __name__ == '__main__':
    unittest.main()
