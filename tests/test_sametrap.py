"""A case marked same_trap accepts the same trapa stop on both sides (scripts/tools/equiv.py same_trap). No game data, no compiler.
Stdlib only.

An error trap (`trapa #48`) is a stop the original reaches by design. Both sides stop on it, but not at the same address: the
original's trap is in the game's code, the C's is in the compiled copy. The simulator reports `trapa #48 at <address>`, so the
two stop messages never match as written. With same_trap in the case, two stops on the same trap number are equal and the
address is not compared; what each side did before the trap still is.

    same      both stop on the same trap number at different addresses: the C's stop becomes the original's
    number    different trap numbers stay different
    marked    a case without same_trap is left alone
    one       a stop on one side only, or another kind of stop, is left alone
    kept      the calls and writes made before the trap are kept
"""
import os
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')

ORIG = {'error': 'trapa #48 at 0C010004', 'calls': [(1, 2)], 'writes': [(3, 4)]}
MINE = {'error': 'trapa #48 at 0C0200FC', 'calls': [(1, 2)], 'writes': [(3, 4)]}


class TestSameTrap(unittest.TestCase):
    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        modules = dict(sys.modules)
        self.addCleanup(self.restore_modules, modules)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(tmp.name)
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        sys.modules.pop('equiv', None)
        import equiv
        self.equiv = equiv

    @staticmethod
    def restore_modules(modules):
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]

    def test_the_same_trap_at_different_addresses_is_one_stop(self):
        got = self.equiv.same_trap({'same_trap': True}, ORIG, MINE)
        self.assertEqual(got['error'], ORIG['error'])

    def test_different_trap_numbers_stay_different(self):
        other = dict(MINE, error='trapa #49 at 0C0200FC')
        self.assertEqual(self.equiv.same_trap({'same_trap': True}, ORIG, other), other)

    def test_a_case_without_same_trap_is_left_alone(self):
        self.assertEqual(self.equiv.same_trap({}, ORIG, MINE), MINE)

    def test_a_stop_on_one_side_only_is_left_alone(self):
        clean = dict(MINE, error=None)
        self.assertEqual(self.equiv.same_trap({'same_trap': True}, ORIG, clean), clean)

    def test_another_kind_of_stop_is_left_alone(self):
        fault = dict(MINE, error='address error at 0C0200FC')
        self.assertEqual(self.equiv.same_trap({'same_trap': True}, ORIG, fault), fault)

    def test_what_happened_before_the_trap_is_kept(self):
        got = self.equiv.same_trap({'same_trap': True}, ORIG, dict(MINE, calls=[(9, 9)]))
        self.assertEqual(got['calls'], [(9, 9)])


if __name__ == '__main__':
    unittest.main()
