#!/usr/bin/env python3
"""The manual-only flag (scripts/tools/consistency.py manual, manual_names): a function written by hand carries a comment
`/* manual: <reason> */` just above its definition, and the tools that write C (shrink.py, hoist.py, the generator's
recheck and rebuild in keep.py) leave it alone. No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/ files:
                    marked     the comment right above the definition: the reason is found, and manual_names lists it
                    unmarked   a function without the comment, or one whose comment belongs to the function before it: None
                    multiline  a reason over two lines is found whole
                    tools      shrink.py, hoist.py and keep.py ask consistency.manual_names() and skip what it lists
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import consistency  # noqa: E402

SRC = ('int helper(int a)\n{\n    return a;\n}\n\n'
       '/* manual: written by hand from the port */\nint rewritten(int mode)\n{\n    return mode + 1;\n}\n\n'
       'int plain(int a)\n{\n    return a * 2;\n}\n\n'
       '/* manual: a hand fix,\n   kept over two lines */\nint fixed(void)\n{\n    return 0;\n}\n')


def main():
    bad = []
    if consistency.manual(SRC, 'rewritten') != 'written by hand from the port':
        bad.append('marked: %r' % consistency.manual(SRC, 'rewritten'))
    for n in ('helper', 'plain'):
        if consistency.manual(SRC, n) is not None:
            bad.append('unmarked %s: %r' % (n, consistency.manual(SRC, n)))
    if 'kept over two lines' not in (consistency.manual(SRC, 'fixed') or ''):
        bad.append('multiline: %r' % consistency.manual(SRC, 'fixed'))
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'a.c'), 'w').write(SRC)
        os.chdir(tmp)
        got = consistency.manual_names()
        if sorted(got) != ['fixed', 'rewritten']:
            bad.append('manual_names: %s' % got)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    for rel in ('7-reduction/shrink.py', '7-reduction/hoist.py', '5-generated/gen_equiv/keep.py'):
        if 'manual_names()' not in open(os.path.join(TOOLS, rel)).read():
            bad.append('tools: %s does not ask manual_names()' % rel)
    if bad:
        sys.exit('[ERROR] manual check failed:\n' + '\n'.join(bad))
    print('[manual] ok: a function marked /* manual: ... */ is found with its reason, others are not, and the tools that write C skip it')


if __name__ == '__main__':
    main()
