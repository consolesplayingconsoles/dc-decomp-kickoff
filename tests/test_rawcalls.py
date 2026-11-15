"""rawcalls.py: C that calls original code by a raw address no function in functions.txt starts at (scripts/tools/5-generated/rawcalls.py).
No game data, no compiler. Stdlib only.

equiv.py passes C such as `((int (*)(int))(0xC0D40CC))(a4)`, since its simulator runs the original bytes at that address, but no C
exists there, so a build from C has nothing to call. The check fails a raw call to an address nobody lists, except those on a
ratchet list (tests/rawcalls_allowed.txt) that only shrinks.

    listed     a raw call to an address a function starts at is not reported, in the 0C or the 8C form of the address
    layout     files are read anywhere under src/, flat or in a tree
    range      a constant outside main RAM is not a call target
    unlisted   a raw call to an address nothing starts at fails, naming the caller and the file
    unit       a file whose first line is `/* @unit` is not read
    allow      --allow records what occurs now; the next plain run passes
    new        a raw call added after --allow fails
    update     --update drops the entries a fix removed, and never adds
    list       --list prints every raw call, the unlisted new ones marked NEW
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'rawcalls.py')

LISTED_CALL = 'int caller_ok(int a4)\n{\n    return ((int (*)(int))(0xC010000))(a4);\n}\n'
RAW_CALL = 'int caller_raw(int a4)\n{\n    return ((int (*)(int))(0xC0D40CC))(a4);\n}\n'
ANOTHER = 'int caller_two(int a4)\n{\n    return ((int (*)(int))(0xC0D5000))(a4);\n}\n'


class TestRawcalls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = self.tmp.name
        os.makedirs(os.path.join(self.repo, 'tools', '5-generated'))
        os.makedirs(os.path.join(self.repo, 'tests'))
        os.makedirs(os.path.join(self.repo, 'src', 'game'))
        shutil.copy(TOOL, os.path.join(self.repo, 'tools', '5-generated', 'rawcalls.py'))
        with open(os.path.join(self.repo, 'functions.txt'), 'w') as f:
            f.write('F 0c010000 32 listed_fn\n')

    def source(self, name, text, folder=os.path.join('src', 'game')):
        os.makedirs(os.path.join(self.repo, folder), exist_ok=True)
        with open(os.path.join(self.repo, folder, name), 'w') as f:
            f.write(text)

    def run_tool(self, *args):
        done = subprocess.run([sys.executable, os.path.join(self.repo, 'tools', '5-generated', 'rawcalls.py')] + list(args),
                              cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return done.returncode, done.stdout, done.stderr

    def allowed(self):
        with open(os.path.join(self.repo, 'tests', 'rawcalls_allowed.txt')) as f:
            return [l.split() for l in f if l.strip() and not l.startswith('#')]

    def test_call_to_a_listed_function_is_not_reported(self):
        self.source('a.c', LISTED_CALL)
        code, out, err = self.run_tool()
        self.assertEqual(code, 0, err)
        self.assertIn('0 raw calls', out)

    def test_the_8c_form_of_a_listed_address_is_not_reported(self):
        self.source('a.c', 'int caller_8c(int a4)\n{\n    return ((int (*)(int))(0x8C010000))(a4);\n}\n')
        code, out, err = self.run_tool()
        self.assertEqual(code, 0, err)

    def test_the_8c_form_of_an_unlisted_address_fails(self):
        self.source('a.c', 'int caller_8c(int a4)\n{\n    return ((int (*)(int))(0x8C0D40CC))(a4);\n}\n')
        code, out, err = self.run_tool()
        self.assertEqual(code, 1)
        self.assertIn('caller_8c', err)

    def test_a_flat_src_layout_is_read(self):
        self.source('a.c', RAW_CALL, folder='src')
        code, out, err = self.run_tool()
        self.assertEqual(code, 1)
        self.assertIn('caller_raw', err)

    def test_a_constant_outside_main_ram_is_not_a_target(self):
        self.source('a.c', 'int caller_io(int a4)\n{\n    return ((int (*)(int))(0xA05F7000))(a4);\n}\n')
        code, out, err = self.run_tool()
        self.assertEqual(code, 0, err)

    def test_call_to_an_unlisted_address_fails_naming_caller_and_file(self):
        self.source('a.c', RAW_CALL)
        code, out, err = self.run_tool()
        self.assertEqual(code, 1)
        self.assertIn('caller_raw', err)
        self.assertIn('0c0d40cc', err)
        self.assertIn(os.path.join('src', 'game', 'a.c'), err)

    def test_a_unit_file_is_not_read(self):
        self.source('u.c', '/* @unit byte-matching */\n' + RAW_CALL)
        code, out, err = self.run_tool()
        self.assertEqual(code, 0, err)

    def test_allow_records_what_occurs_and_the_next_run_passes(self):
        self.source('a.c', RAW_CALL)
        self.assertEqual(self.run_tool('--allow')[0], 0)
        self.assertEqual(self.allowed(), [['0c0d40cc', 'caller_raw', os.path.join('src', 'game', 'a.c')]])
        self.assertEqual(self.run_tool()[0], 0)

    def test_a_raw_call_added_after_allow_fails(self):
        self.source('a.c', RAW_CALL)
        self.run_tool('--allow')
        self.source('b.c', ANOTHER)
        code, out, err = self.run_tool()
        self.assertEqual(code, 1)
        self.assertIn('caller_two', err)
        self.assertNotIn('caller_raw', err)

    def test_update_drops_the_fixed_entries_and_never_adds(self):
        self.source('a.c', RAW_CALL)
        self.source('b.c', ANOTHER)
        self.run_tool('--allow')
        self.source('a.c', LISTED_CALL)
        self.source('c.c', 'int caller_new(int a4)\n{\n    return ((int (*)(int))(0xC0D6000))(a4);\n}\n')
        code, out, err = self.run_tool('--update')
        self.assertEqual(code, 1)                           # the new call still fails
        self.assertEqual([e[1] for e in self.allowed()], ['caller_two'])

    def test_list_marks_the_unlisted_new_calls(self):
        self.source('a.c', RAW_CALL)
        self.source('b.c', ANOTHER)
        self.run_tool('--allow')
        self.source('c.c', 'int caller_new(int a4)\n{\n    return ((int (*)(int))(0xC0D6000))(a4);\n}\n')
        code, out, err = self.run_tool('--list')
        lines = [l for l in out.split('\n') if 'caller_' in l]
        self.assertEqual(len(lines), 3)
        self.assertEqual([('NEW' in l) for l in lines].count(True), 1)


if __name__ == '__main__':
    unittest.main()
