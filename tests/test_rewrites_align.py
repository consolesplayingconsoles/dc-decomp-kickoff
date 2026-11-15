"""A one-field structure member is only written where its type aligns (scripts/tools/5-generated/gen_equiv/rewrites.py struct_access and
global_base). No game data, no compiler. Stdlib only.

`struct oN_T { char p[N]; T v; }` puts `v` at N only when N is a multiple of T's size: the compiler pads it up to the next one, so
`o13_float` would land at 0x14 and the access would read or write one byte late. An access at an offset its type does not align to
is left as the plain pointer access it was; an aligned one is still rewritten.

    struct_access   float   a float at 0x13 stays a pointer access, one at 0x14 becomes a member
                    short   a short at an odd offset stays, at an even one becomes a member
                    char    a char has no alignment: any offset past the short form becomes a member
    global_base     float   of two nearby floats, the one at an offset not a multiple of 4 from the lowest address stays
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


class TestRewritesAlign(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import rewrites
        self.rewrites = rewrites

    def access(self, ctype, offset):
        return 'void f(int a4)\n{\n    *(%s *)((a4 + 0x%X)) = 1;\n}\n' % (ctype, offset)

    def test_float_at_a_misaligned_offset_stays_a_pointer_access(self):
        text = self.access('float', 0x13)
        self.assertEqual(self.rewrites.struct_access(text), text)

    def test_float_at_an_aligned_offset_becomes_a_member(self):
        self.assertIn('struct o14_float', self.rewrites.struct_access(self.access('float', 0x14)))

    def test_short_at_an_odd_offset_stays_a_pointer_access(self):
        text = self.access('short', 0x41)
        self.assertEqual(self.rewrites.struct_access(text), text)

    def test_short_at_an_even_offset_becomes_a_member(self):
        self.assertIn('struct o42_short', self.rewrites.struct_access(self.access('short', 0x42)))

    def test_char_at_any_offset_past_the_short_form_becomes_a_member(self):
        self.assertIn('struct o11_char', self.rewrites.struct_access(self.access('char', 0x11)))

    def test_global_float_at_a_misaligned_offset_from_the_base_stays(self):
        text = 'void f(void)\n{\n    *(float *)0xC94D960 = 1;\n    *(float *)0xC94D963 = 2;\n    *(float *)0xC94D964 = 3;\n}\n'
        got = self.rewrites.global_base(text)
        self.assertIn('*(float *)0xC94D963', got)          # offset 3: left as it was
        self.assertIn('struct o4_float', got)              # offset 4: a member
        self.assertNotIn('struct o3_float', got)


if __name__ == '__main__':
    unittest.main()
