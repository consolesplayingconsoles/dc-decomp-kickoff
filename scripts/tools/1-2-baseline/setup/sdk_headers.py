#!/usr/bin/env python3
"""Copy an SDK's C headers in a form Ghidra's C parser reads. Stdlib only.

    sdk_headers.py <SDK folder> <out folder>

Finds the include folders by name (shinobi/include, shc/include, and their subfolders) and writes
each header under <out folder>/<same relative path>, with the 1990s habits the parser trips on
taken out: form feeds between declarations, Shift-JIS comment text (replaced by '?', the code is
untouched), `(Void)`, `(VOID)` and every other typedef of void as an empty parameter list (-> `(void)`; the typedefs stay), and a
`machine.h` stub for the SHC intrinsics header that is not shipped as such, and the empty
calling-convention and direction macros (`KMAPI`, `KMAPIENTRY`, `CRIAPI`, `IN`, `OUT`) dropped
from declarations. Then:

    ghidra/ApplyHeaders.java <out>/shinobi/include <out>/shinobi/include/SHC <out>/shc/include <out>/stub -D__SHC__ -D_SH4
"""
import os
import re
import sys

if len(sys.argv) != 3:
    sys.exit(__doc__)
sdk, out = sys.argv[1], sys.argv[2]
# every typedef of void (Void, VOID, KMVOID...): as a sole parameter it must read (void)
void_names = set()
for root, dirs, files in os.walk(sdk):
    for name in files:
        if name.lower().endswith('.h'):
            try:
                t = open(os.path.join(root, name), encoding='latin-1').read()
                void_names |= set(re.findall(r'typedef\s+void\s+(\w+)\s*;', t))
                void_names |= set(re.findall(r'#\s*define\s+(\w+)\s+(?:void|VOID|Void)\s*(?:/\*.*)?$', t, re.M))   # macro aliases
            except OSError:
                pass
texts = []
for root, dirs, files in os.walk(sdk):
    for name in files:
        if name.lower().endswith('.h'):
            try:
                texts.append(open(os.path.join(root, name), encoding='latin-1').read())
            except OSError:
                pass
void_names |= {'Void'}
while True:                                                      # aliases of aliases (KMVOID -> VOID -> void)
    more = set()
    for t in texts:
        for m in re.finditer(r'(?:typedef\s+(\w+)\s+(\w+)\s*;|#\s*define\s+(\w+)\s+(\w+)\s*(?:/[/*].*)?$)', t, re.M):
            src, dst = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
            if src in void_names and dst not in void_names:
                more.add(dst)
    if not more:
        break
    void_names |= more
void_param = re.compile(r'\(\s*(%s)\s*\)' % '|'.join(sorted(void_names)))
n = 0
for root, dirs, files in os.walk(sdk):
    rel = os.path.relpath(root, sdk)
    if not re.search(r'(^|/)(include)($|/)', rel.replace(os.sep, '/')):
        continue
    for name in files:
        if not name.lower().endswith('.h'):
            continue
        src = os.path.join(root, name)
        data = open(src, 'rb').read()
        text = data.decode('latin-1')
        text = text.replace('\r\n', '\n').replace('\x0c', '\n')
        text = re.sub(r'[\x80-\xff]', '?', text)                      # comment text in Shift-JIS
        text = void_param.sub('(void)', text)
        text = re.sub(r'\b(KMAPI|KMAPIENTRY|CRIAPI|IN|OUT)\b(?!\s*[=(])', ' ', text)   # calling-convention and direction macros
        dest = os.path.join(out, rel, name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='ascii') as f:
            f.write(text)
        n += 1
stub = os.path.join(out, 'stub')
os.makedirs(stub, exist_ok=True)
with open(os.path.join(stub, 'machine.h'), 'w') as f:
    f.write('/* stub: SHC intrinsics, not needed for prototypes */\n#include <smachine.h>\n#include <umachine.h>\n')
print('%d headers -> %s (plus stub/machine.h)' % (n, out))
