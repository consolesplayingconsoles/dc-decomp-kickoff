#!/usr/bin/env python3
"""A case may name callees that run on both sides ("real": ["memcpy", "memset"]): a runtime helper that runs inline copies
and clears its locals through them, and mocked they leave it working on stack leftovers. An unknown name is an error.
No game data. Stdlib only."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import equiv  # noqa: E402

TABLE = {'memcpy': 0x8C013000, 'memset': 0x8C013100, '_div': 0x8C010000, 'other': 0x8C014000}


class Real(unittest.TestCase):
    def test_named_callees_run_with_the_helpers(self):
        base = lambda t: t == 0x8C010000
        deep = equiv.with_real(base, {'real': ['memcpy']}, TABLE)
        self.assertTrue(deep(0x8C010000))
        self.assertTrue(deep(0x8C013000))
        self.assertTrue(deep(0x0C013000))
        self.assertFalse(deep(0x8C013100))
        self.assertFalse(deep(0x8C014000))

    def test_no_key_changes_nothing(self):
        base = lambda t: False
        self.assertIs(equiv.with_real(base, {}, TABLE), base)

    def test_unknown_name_stops(self):
        with self.assertRaises(SystemExit):
            equiv.with_real(lambda t: False, {'real': ['nope']}, TABLE)


if __name__ == '__main__':
    unittest.main()
