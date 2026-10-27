#!/usr/bin/env python3
"""The compiled-object cache (scripts/tools/8-build/buildcache.py): an object is reused only when everything it came from is the same.
No compiler, no game data: fake objects. Stdlib only.

    check.py      a temp folder where:
                    hit        a stored object (with its .s and optimizer info) comes back byte for byte, into objd and objd/shciop
                    miss       a key never stored is a miss and writes nothing
                    source     one changed byte of the C text is another key
                    header     a header changed under the folders hashed is another key; a header elsewhere is not
                    flags      other compiler flags (or the build script's compile step) are another key
                    nothing    store of a stem that has no object keeps nothing and says so
                    half       an entry with extras but no .obj (an interrupted store) is not a hit
                    include    a file is keyed on the headers it includes (and theirs): a header it does not include changes nothing (a
                               mod's layer adds src/tux.h: with every header hashed, no object of the decomp's cache was reusable)
                    compiler   another shc.exe, asmsh.exe or SDK header is another key (SDK_PATH pointed elsewhere returned the old
                               compiler's objects)
                    cachedir   BUILD_CACHE sets where the cache is (a mod's tree shares the decomp's)
                    pieces     cbuild keys an assembly piece on its build step, not on a fixed string
                    name       the same text under another file name is another key: the compiler writes the file's name into the
                               object as its module (a one-file unit u019.c, a copy of gen_xx.c, got gen_xx's object: the link listed
                               module gen_xx, and the fit found no size for u019, Crazy Taxi tux-racer)
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build'))
import buildcache as C  # noqa: E402

fails = []


def check(name, ok):
    print('%-8s %s' % (name, 'ok' if ok else 'FAIL'))
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory() as t:
    root = os.path.join(t, 'ccache')
    src = os.path.join(t, 'src')
    other = os.path.join(t, 'other')
    os.makedirs(src)
    os.makedirs(other)
    open(os.path.join(src, 'a.h'), 'w').write('#define A 1\n')
    objd = os.path.join(t, 'obj')
    os.makedirs(os.path.join(objd, 'shciop'))
    open(os.path.join(objd, 'f.obj'), 'wb').write(b'\x01\x02OBJ')
    open(os.path.join(objd, 'f.s'), 'wb').write(b'asm text')
    open(os.path.join(objd, 'shciop', 'f.iop'), 'wb').write(b'iop')
    hh = C.headers_hash([src])
    k = C.key('int f(void){return 1;}', '-cpu=sh4', hh, 'v1')
    check('nothing', C.store(k, objd, 'absent', root) is False and not os.path.exists(root))
    check('miss', C.restore(k, os.path.join(t, 'o2'), 'f', root) is False and not os.path.exists(os.path.join(t, 'o2')))
    check('store', C.store(k, objd, 'f', root) is True)
    o2 = os.path.join(t, 'o2')
    ok = C.restore(k, o2, 'f', root)
    check('hit', ok and open(os.path.join(o2, 'f.obj'), 'rb').read() == b'\x01\x02OBJ'
          and open(os.path.join(o2, 'f.s'), 'rb').read() == b'asm text' and open(os.path.join(o2, 'shciop', 'f.iop'), 'rb').read() == b'iop')
    check('source', C.key('int f(void){return 2;}', '-cpu=sh4', hh, 'v1') != k)
    open(os.path.join(src, 'a.h'), 'w').write('#define A 2\n')
    check('header', C.headers_hash([src]) != hh)
    open(os.path.join(other, 'z.h'), 'w').write('#define Z 1\n')
    check('header2', C.headers_hash([src]) == C.headers_hash([src]) and C.headers_hash([src, other]) != C.headers_hash([src]))
    check('flags', C.key('int f(void){return 1;}', '-cpu=sh4 -goptimize', hh, 'v1') != k and C.key('int f(void){return 1;}', '-cpu=sh4', hh, 'v2') != k)
    k2 = C.key('x', '', '', '')
    os.makedirs(root, exist_ok=True)
    open(os.path.join(root, k2 + '.iop'), 'wb').write(b'x')
    check('half', C.restore(k2, os.path.join(t, 'o3'), 'x', root) is False)
    inc = os.path.join(t, 'inc')
    os.makedirs(inc)
    open(os.path.join(inc, 'a.h'), 'w').write('#include "b.h"\n')
    open(os.path.join(inc, 'b.h'), 'w').write('#define B 1\n')
    open(os.path.join(inc, 'tux.h'), 'w').write('#define T 1\n')
    ctext = '#include "a.h"\nint f(void) { return B; }\n'
    i0 = C.includes_hash(ctext, [inc])
    open(os.path.join(inc, 'tux.h'), 'w').write('#define T 2\n')
    check('include', C.includes_hash(ctext, [inc]) == i0)
    open(os.path.join(inc, 'b.h'), 'w').write('#define B 2\n')
    check('include2', C.includes_hash(ctext, [inc]) != i0)
    sdk = os.path.join(t, 'sdk', 'bin')
    os.makedirs(sdk)
    for n, b in (('shc.exe', b'shc1'), ('asmsh.exe', b'asm1')):
        open(os.path.join(sdk, n), 'wb').write(b)
    open(os.path.join(sdk, 'machine.h'), 'w').write('x')
    c0 = C.tools_hash(os.path.join(t, 'sdk'), 'bin')
    open(os.path.join(sdk, 'shc.exe'), 'wb').write(b'shc2')
    c1 = C.tools_hash(os.path.join(t, 'sdk'), 'bin')
    open(os.path.join(sdk, 'machine.h'), 'w').write('y')
    check('compiler', c0 != c1 and C.tools_hash(os.path.join(t, 'sdk'), 'bin') != c1)
import subprocess  # noqa: E402
env = dict(os.environ, BUILD_CACHE='/tmp/somewhere-shared')
out = subprocess.run([sys.executable, '-c', 'import sys; sys.path.insert(0, %r); import buildcache; print(buildcache.CACHE)'
                      % os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build')], env=env,
                     stdout=subprocess.PIPE, universal_newlines=True).stdout.strip()
check('cachedir', out == '/tmp/somewhere-shared')
cb = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build', 'cbuild.py')).read()
check('name', C.key('int f(void){return 1;}', '-cpu=sh4', '', 'v1', name='u019') != C.key('int f(void){return 1;}', '-cpu=sh4', '', 'v1', name='gen_xx'))
check('cbname', 'name=s_' in cb and 'name=name' in cb)
check('pieces', "'asmsh -cpu=sh4 -endian=little', '', 'piece'" not in cb and 'buildcache.includes_hash(' in cb and 'buildcache.tools_hash(' in cb)
sys.exit(1 if fails else 0)
