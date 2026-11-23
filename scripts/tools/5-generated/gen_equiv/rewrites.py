"""Rewrites of generated C that change no address and no type, for size: the generator's last passes (gen_drv.py) and the
`--passes` strategies of tools/7-reduction/shrink.py. Stdlib only.

    drop_self_copies   a stack slot copied onto itself
    struct_access      far field accesses as members of one-field structures
    global_base        nearby fixed addresses as members off the lowest of them
    struct_decls       the declarations the two above need
    splice             a unit's text with rewritten functions in place and those declarations after its head
"""
import layout  # noqa: E402  (tools/toolpath.py has put tools/ on the path)
import re

_SELF = re.compile(r'^[ \t]*\*\(((?:unsigned )?(?:int|short|char|float)) \*\)\(\(\(int\)stk \+ (\d+)\)\) = '
                   r'\*\(((?:unsigned )?(?:int|short|char|float)) \*\)\(\(int\)stk \+ (\d+)\);\n', re.M)


def drop_self_copies(text):
    """`*(unsigned int *)(((int)stk + 28)) = *(int *)((int)stk + 28);`, a frame slot stored back with the value just read from it,
    left by register shuffles the generator wrote out (Zombie Revenge: 2,094 in 47 functions, FUN_0c065bb2 1,700 bytes to 1,224).
    It is a load and a store to the function's own frame that change nothing, so the line goes. Only the same slot at the same
    width; a narrowing or widening copy stays."""
    return _SELF.sub(lambda m: '' if m.group(2) == m.group(4) and m.group(1).replace('unsigned ', '') == m.group(3).replace('unsigned ', '')
                     else m.group(0), text)




def struct_access(text):
    """A field read or written at an offset past the short displacement form, `*(int *)((a4 + 0x2D4))`, as a member of a one-field
    structure, `((struct o2D4_int *)(a4))->v` (struct_decls lists the declarations). SHC compiles the first as integer arithmetic: it
    keeps the offsets in saved registers and adds one to the base for every access (Zombie Revenge FUN_0c031e5e: four offsets in r8-r12,
    four more pushes, the argument spilled); the member compiles as the original's `mov.w #off,r0; mov.l @(r0,Rn)`, as `p->field` does
    (360 bytes of C to 296). The short form reaches 60 bytes for an int, 30 for a short, 15 for a char; a float has none. A volatile
    access is left (the member is not volatile), and so is a base declared as a pointer or an array, whose + scales."""
    lim={'int':60,'unsigned int':60,'short':30,'unsigned short':30,'char':15,'unsigned char':15,'float':0}
    head=text.split('{',1)[0]
    scaled=set(re.findall(r'\*\s*(\w+)\s*[,)]',head))|set(re.findall(r'^\s*(?:register )?[\w ]+?\*\s*(\w+);$',text,re.M))|set(re.findall(r'\b(\w+)\[\d*\];',text))
    pat=re.compile(r'\*\((volatile )?((?:unsigned )?(?:int|short|char|float)) \*\)\(')
    def close(s,i):
        d=0
        for j in range(i,len(s)):
            d+=(s[j]=='(')-(s[j]==')')
            if d==0: return j
        return -1
    def plus(e):
        d=0;last=-1
        for j,ch in enumerate(e):
            d+=(ch=='(')-(ch==')')
            if d==0 and e[j:j+3]==' + ': last=j
        return last
    def walk(s):
        out=[];i=0
        while True:
            m=pat.search(s,i)
            if not m: out.append(s[i:]); return ''.join(out)
            o=m.end()-1; c=close(s,o)
            if c<0: out.append(s[i:]); return ''.join(out)
            inner=s[o+1:c]
            while inner.startswith('(') and close(inner,0)==len(inner)-1: inner=inner[1:-1]
            while True:                       # `((0xC0 + a4) + 0x0)`: the + 0x0 wrapper goes, and the constant goes last
                k=plus(inner)
                if k>0 and re.fullmatch(r'\s*0x0+\s*',inner[k+3:]):
                    inner=inner[:k].strip()
                    while inner.startswith('(') and close(inner,0)==len(inner)-1: inner=inner[1:-1]
                    continue
                if k>0 and not re.fullmatch(r'\s*0x[0-9A-Fa-f]+\s*',inner[k+3:]) and re.fullmatch(r'\s*0x[0-9A-Fa-f]+\s*',inner[:k]) and plus(inner[:k])<0:
                    inner=inner[k+3:].strip()+' + '+inner[:k].strip()
                break
            k=plus(inner); ty=m.group(2)
            off=re.fullmatch(r'\s*0x([0-9A-Fa-f]+)\s*',inner[k+3:]) if k>0 else None
            base=inner[:k].strip() if k>0 else ''
            if (m.group(1) or not off or not lim[ty]<int(off.group(1),16)<0x10000 or int(off.group(1),16) % _TSIZE.get(ty, 1) or base in scaled
                    or re.fullmatch(r'\(*(\w+)\)*',base) and re.fullmatch(r'\(*(\w+)\)*',base).group(1) in scaled):
                out.append(s[i:o+1]); i=o+1; continue
            out.append(s[i:m.start()])
            out.append('(((struct o%X_%s *)(%s))->v)'%(int(off.group(1),16),ty.replace('unsigned ','u'),walk(base)))
            i=c+1
    return walk(text)
# a one-field structure `struct oN_T { char p[N]; T v; }` puts v at N only when N is a multiple of T's size: the compiler pads it
# to the next one (o13_float lands at 0x14), so an access at a misaligned offset stays a plain pointer access
_TSIZE = {'int': 4, 'unsigned int': 4, 'float': 4, 'short': 2, 'unsigned short': 2}


def global_base(text, span=60):
    """Globals a function reaches at nearby fixed addresses, `*(int *)0xC94D964`, as members off the lowest of them,
    `((struct o4_int *)0xC94D960)->v`, where two or more lie within span bytes of it. SHC loads each fixed address from the pool and
    reads through it; the shared base is loaded once and the others are displacements from it, as the original reached the fields of one
    global structure (four such globals: 36 bytes of C to 20). A volatile access is left as it is."""
    pat=re.compile(r'\*\(((?:unsigned )?(?:int|short|char|float)) \*\)(0x[0-9A-Fa-f]{7,8})\b')
    addrs=sorted({int(m.group(2),16) for m in pat.finditer(text)})
    base={};i=0
    while i<len(addrs):
        j=i
        while j+1<len(addrs) and addrs[j+1]-addrs[i]<=span: j+=1
        if j>i:
            for a in addrs[i:j+1]: base[a]=addrs[i]
        i=j+1
    def sub(m):
        a=int(m.group(2),16)
        if a not in base or (a-base[a]) % _TSIZE.get(m.group(1), 1): return m.group(0)      # a member at an offset its type does not align
        return '(((struct o%X_%s *)0x%X)->v)'%(a-base[a],m.group(1).replace('unsigned ','u'),base[a])
    return pat.sub(sub,text) if base else text

_SMOD = re.compile(
    r'^(?P<ind>[ \t]*)if \(\(int\)(?P<v>\w+) >= 0\) \{\n'
    r'[ \t]*(?P=v) = \((?P=v) & (?P<m>0x[0-9A-Fa-f]+)\);\n'
    r'[ \t]*\} else \{\n'
    r'[ \t]*(?P=v) = \(~(?P=v)\);\n'
    r'[ \t]*(?P=v) = \((?P=v) \+ 0x1\);\n'
    r'[ \t]*(?P=v) = \((?P=v) & (?P=m)\);\n'
    r'[ \t]*(?P=v) = \(~(?P=v)\);\n'
    r'[ \t]*(?P=v) = \((?P=v) \+ 0x1\);\n'
    r'[ \t]*\}\n', re.M)


_SMOD2 = re.compile(
    r'^(?P<ind>[ \t]*)(?P<d>\w+) = \(\(~\(\(\(~(?P<s>\w+)\) \+ 0x1\) & (?P<m>0x[0-9A-Fa-f]+)\)\) \+ 0x1\);\n'
    r'[ \t]*if \(\(int\)(?P=s) >= 0\) \{\n'
    r'[ \t]*(?P=d) = \((?P=s) & (?P=m)\);\n'
    r'[ \t]*\}\n', re.M)


def fold_signed_mask(text):
    """The sign sequences the generator writes for a remainder by a power of two on a signed value, as one `% 0x40` line. Two shapes:
    `if ((int)t5 >= 0) { t5 = (t5 & 0x3F); } else { t5 = (~t5); t5 = (t5 + 0x1); t5 = (t5 & 0x3F); t5 = (~t5); t5 = (t5 + 0x1); }`
    becomes `t5 = (t5 % 0x40);`, and `t9 = ((~(((~t5) + 0x1) & 0xF)) + 0x1); if ((int)t5 >= 0) { t9 = (t5 & 0xF); }` becomes
    `t9 = (t5 % 0x10);` (t9 another variable than t5). Both compute the same value as C's remainder on a signed int, but that is
    not what lets the rewrite stay: shrink.py keeps it only when the unit compiles smaller and equiv.py proves the function
    on the simulator, so the Dreamcast's own behaviour decides. Power Stone 2: the first shape 16 times in FUN_0c0d0ec2, the
    second 28 times in FUN_0c0b2d30. Only a mask of the form 2^k - 1 on a variable the function declares `int`."""
    def int_var(m, v):
        head = text[:m.start()]
        f = head.rfind('\n{\n')
        return re.search(r'(?m)^[ \t]*(?:register )?int %s;' % re.escape(v), head[f + 1:] if f >= 0 else head)

    def one(m):
        mask = int(m.group('m'), 16)
        if mask < 1 or mask & (mask + 1) or not int_var(m, m.group('v')):
            return m.group(0)
        return '%s%s = (%s %% 0x%X);\n' % (m.group('ind'), m.group('v'), m.group('v'), mask + 1)

    def two(m):
        mask = int(m.group('m'), 16)
        if mask < 1 or mask & (mask + 1) or m.group('d') == m.group('s') or not int_var(m, m.group('s')):
            return m.group(0)
        return '%s%s = (%s %% 0x%X);\n' % (m.group('ind'), m.group('d'), m.group('s'), mask + 1)
    out = _SMOD.sub(one, text)
    text = out
    return _SMOD2.sub(two, out)


def struct_decls(text):
    """The declarations of the structures struct_access and global_base name in text, each once, ordered by name."""
    ty={'int':'int','uint':'unsigned int','short':'short','ushort':'unsigned short','char':'char','uchar':'unsigned char','float':'float'}
    return ['struct o%s_%s { %s%s v; };'%(o,t,'' if o=='0' else 'char p[0x%s]; '%o,ty[t]) for o,t in sorted(set(re.findall(r'\bstruct o([0-9A-F]+)_(\w+) \*',text)))]


def splice(text, new):
    """text with each function in new ({name: C}) put in place of its definition, and the one-field structures the file's functions
    now name declared once, after the head (before the first definition)."""
    import consistency
    import sizes
    for name, c in new.items():
        b = consistency.block(text, name)
        if b:
            text = text[:b[0]] + c.rstrip('\n') + '\n' + text[b[1]:]
    head = sizes.unit_head(text)
    have = set(re.findall(r'^struct o[0-9A-F]+_\w+ \{.*\};$', head, re.M))
    add = [d for d in struct_decls(text[len(head):]) if d not in have]
    if add:
        text = head.rstrip('\n') + '\n' + '\n'.join(add) + '\n' + text[len(head):]
    return text


def _params(arglist):
    """The parameter types of a prototype's or definition's argument list ('int a4, float f4' -> ['int', 'float'])."""
    a = arglist.strip()
    if a in ('', 'void'):
        return []
    out = []
    for x in a.split(','):
        x = ' '.join(x.split())
        m = re.match(r'^(.*[\w*])\s+([A-Za-z_]\w*)$', x)
        types = ('int', 'float', 'short', 'char', 'unsigned', 'signed', 'long', 'double')
        out.append(m.group(1) if m and m.group(2) not in types and not re.match(r'Stk\d+$', m.group(2)) else x)
    return out


def definitions(texts):
    """{function: [parameter types]} of every function defined in the given unit texts."""
    out = {}
    for t in texts:
        for m in re.finditer(r'^[A-Za-z_][\w \t\*]*?\b(\w+)\s*\(([^;{]*)\)\s*\n\{', t, re.M):
            out[m.group(1)] = _params(m.group(2))
    return out


def _args(s):
    out, d, cur = [], 0, ''
    for ch in s:
        d += (ch == '(') - (ch == ')')
        if ch == ',' and d == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


_PROTO = r'^((?:extern )?[A-Za-z_][\w ]*?\b%s)\(([^)]*)\);$'


def _calls(text, n):
    """(open, close, [arguments]) of each call of n in text that is not a declaration line."""
    out = []
    for m in re.finditer(r'(?<![\w*])%s\(' % re.escape(n), text):
        ls = text.rfind('\n', 0, m.start()) + 1
        if re.match(_PROTO % re.escape(n), text[ls:text.find('\n', m.start()) if text.find('\n', m.start()) >= 0 else len(text)]):
            continue
        o, d = m.end() - 1, 0
        for j in range(o, len(text)):
            d += (text[j] == '(') - (text[j] == ')')
            if d == 0:
                break
        out.append((o, j, _args(text[o + 1:j])))
    return out


def _has_call(x):
    return re.search(r'\b(?!int\b|float\b|unsigned\b|short\b|char\b|signed\b)[A-Za-z_]\w*\s*\(', x) is not None


def _all_trimmable(text, n, k):
    """Every call of n passes no more than k arguments, or its arguments past the k-th hold no call (dropping them changes nothing)."""
    return all(len(a) <= k or not any(_has_call(x) for x in a[k:]) for _, _, a in _calls(text, n))


def narrow_calls(text, defs):
    """(text, [names]): each callee the unit declares with more parameters than its own definition takes (defs, from
    definitions) declared as defined, and the extra arguments dropped at its calls. The generator sized some prototypes from what
    its callers left in registers and on the stack (Zombie Revenge FUN_0c0cc3f8: 4 parameters, declared with 12 in 155 units), so
    every call loaded and pushed words the callee never reads; the checker compared them because the prototype said so. Only when
    the declared types start with the definition's and no dropped argument holds a call (a dropped argument has no effect)."""
    names = []
    for m in re.finditer(_PROTO % r'(\w+)', text, re.M):
        n = m.group(2)
        if n in defs and '...' not in m.group(3):
            p = _params(m.group(3))
            if len(p) > len(defs[n]) and p[:len(defs[n])] == defs[n] and _all_trimmable(text, n, len(defs[n])):
                names.append(n)
    for n in names:
        k = len(defs[n])
        lines = text.split('\n')
        protos = {i for i, l in enumerate(lines) if re.match(_PROTO % re.escape(n), l)}
        for i in protos:
            m = re.match(_PROTO % re.escape(n), lines[i])
            lines[i] = '%s(%s);' % (m.group(1), ', '.join(defs[n]) or 'void')
        text = '\n'.join(lines)
        for o, j, a in reversed(_calls(text, n)):
            if len(a) > k:              # the newlines of the dropped arguments stay, after the call: a writer's line spans hold
                text = text[:o + 1] + ','.join(a[:k]).strip() + ')' + '\n' * ''.join(a[k:]).count('\n') + text[j + 1:]
    return text, names


_CAST = re.compile(r'\(\((?P<ret>[A-Za-z_][\w ]*?) \(\*\)\((?P<types>[^()]*)\)\)\((?P<name>\w+)\)\)\(')


def narrow_cast_calls(text, defs):
    """`((int (*)(int, int, int, int, int))(F))(a, b, c, d, e)` with F defined (defs, from definitions) on three parameters as
    `((int (*)(int, int, int))(F))(a, b, c)`. The generator calls a function it has no prototype for through a cast sized from what
    the caller left in registers and on the stack (Power Stone 2 FUN_0c02e43c: a 3-parameter function called six times through a
    12-int cast), so every call loaded and pushed words the callee never reads, and the checker compared them because the cast said
    so. Only when the cast's leading types are the definition's and no dropped argument holds a call. The newlines of dropped
    arguments stay after the call, so a writer's line spans hold."""
    for m in reversed(list(_CAST.finditer(text))):
        n = m.group('name')
        if n not in defs:
            continue
        k = len(defs[n])
        types = _params(m.group('types'))
        if len(types) <= k or types[:k] != defs[n]:
            continue
        o, d = m.end() - 1, 0
        for j in range(o, len(text)):
            d += (text[j] == '(') - (text[j] == ')')
            if d == 0:
                break
        args = _args(text[o + 1:j])
        if len(args) <= k or any(_has_call(x) for x in args[k:]):
            continue
        keep = ', '.join(m.group('types').split(', ')[:k]) or 'void'
        new = '((%s (*)(%s))(%s))(%s)' % (m.group('ret'), keep, n, ','.join(args[:k]).strip()) + '\n' * ''.join(args[k:]).count('\n')
        text = text[:m.start()] + new + text[j + 1:]
    return text


_DEFS = []


def narrow_unit(text):
    """A unit's text (its head of prototypes and the bodies) with every callee declared wider than its own definition narrowed
    (narrow_calls): the generator sizes a prototype from what the caller leaves in r4-r7 and on the stack, and the definition,
    once written, is the truth. The definitions are read from src/ once per process; GEN_NARROW=0 leaves the text as it is.
    The line count is unchanged, so a writer's line spans still hold."""
    import glob
    import os
    if os.environ.get('GEN_NARROW', '1') == '0':
        return text
    if not _DEFS:
        _DEFS.append(definitions(open(p, errors='replace').read() for p in layout.c_files()
                                 if not os.path.basename(p).startswith(('gen_tmp', 'zz_'))))
    return narrow_cast_calls(narrow_calls(text, _DEFS[0])[0], _DEFS[0])


_COPY = re.compile(r'^(\s*)(t\d+) = \(?(t\d+)\)?;$')


def merge_copies(text):
    """`t70 = (t30);` with t30 dead after it: t30 is written as t70 from its first use on and the copy goes. The structured form
    threads a result up through its nesting levels, one temporary and one copy per level (Zombie Revenge FUN_0c02374e: t30 ->
    t70 -> t95 -> t117), and SHC keeps a `mov` for each (4,164 such lines in the game's C). Safe when t30 is never mentioned after
    the copy, t70 is not mentioned from t30's first use to the copy, and no goto, break, continue or label lies in that stretch (a
    jump over the copy would leave t70 with t30's value)."""
    lines = text.split('\n')
    changed = True
    while changed:
        changed = False
        for i, l in enumerate(lines):
            m = _COPY.match(l)
            if not m or m.group(2) == m.group(3):
                continue
            ind, a, b = m.groups()
            rb = re.compile(r'\b%s\b' % b)
            ra = re.compile(r'\b%s\b' % a)
            first = next((k for k, x in enumerate(lines) if rb.search(x) and not re.match(r'^\s*(?:register )?(?:int|float|unsigned int|short|char) %s;$' % b, x)), None)
            if first is None or first >= i:
                continue
            if any(rb.search(x) for x in lines[i + 1:]):
                continue
            if any(ra.search(x) for x in lines[first:i]):
                continue
            if any(re.match(r'^\s*(goto |break;|continue;|\w+:;)', x) for x in lines[first:i]):
                continue
            for k in range(first, i):
                lines[k] = rb.sub(a, lines[k])
            del lines[i]
            lines = [x for x in lines if not re.match(r'^\s*(?:register )?(?:int|float|unsigned int|short|char) %s;$' % b, x)]
            changed = True
            break
    return '\n'.join(lines)


_IFCHAIN = re.compile(r'^(\s*)if \((t\d+|a\d+) (!=|==) (\d+|0x[0-9A-Fa-f]+)\) \{$')


def _block_end(lines, i, ind):
    """Index of the line closing the block opened at line i: the next line at exactly indent ind that starts with '}'."""
    for k in range(i + 1, len(lines)):
        x = lines[k]
        if x.strip() and len(x) - len(x.lstrip()) == ind and x.lstrip().startswith('}'):
            return k
    return None


def _chain(lines, i, var=None):
    """(arms, rest, end) of the if-chain on one variable starting at line i: arms [(value, body lines, their indent)], rest the
    lines no arm took (the innermost then-block of a != chain, or else-block of a == chain) with its indent, end the index of the
    chain's last line; None when line i is no chain level on var or the chain is broken."""
    m = _IFCHAIN.match(lines[i])
    if not m or (var and m.group(2) != var):
        return None
    ind, v, op, val = len(m.group(1)), m.group(2), m.group(3), m.group(4)
    close = _block_end(lines, i, ind)
    if close is None:
        return None
    has_else = lines[close].strip() == '} else {'
    end = _block_end(lines, close, ind) if has_else else close
    if end is None:
        return None
    then_b, else_b = lines[i + 1:close], (lines[close + 1:end] if has_else else [])
    if not has_else and op == '!=' and var is not None:
        # the innermost level of a chain: `if (t0 != 8) { return t0; } ARM8` (the then-block always leaves, no label in it)
        last = next((x.strip() for x in reversed(then_b) if x.strip()), '')
        if re.match(r'^(return\b|goto\b)', last) and not any(re.match(r'^\s*\w+:;', x) for x in then_b):
            return [(val, lines[close + 1:], ind)], (then_b, ind + 4), len(lines) - 1
        return None
    arm, nxt = (else_b, then_b) if op == '!=' else (then_b, else_b)
    arms = [(val, arm, ind + 4)]
    k = next((q for q, x in enumerate(nxt) if x.strip()), None)
    sub = _chain(nxt, k, v) if k is not None and (op == '!=' or has_else) else None
    if sub and sub[2] == len(nxt) - 1 and all(not x.strip() for x in nxt[:k]):
        arms += sub[0]
        rest = sub[1]
    else:
        rest = (nxt, ind + 4)
    return arms, rest, end


def chains_to_switch(text, minlen=3):
    """A chain of `if (t0 != 0) { if (t0 != 1) { ... } else { ARM1 } } else { ARM0 }` (or the == form) on one variable, three
    levels or more, as a switch: SHC emits `mov r4,r0; cmp/eq #k; bf; bra; nop` for each level of the chain and `cmp/eq #k; bt`
    for a case (Zombie Revenge FUN_0c0b1330: a nine-state chain; 869 such ifs in 176 functions). Left as it is when an arm holds a
    `break;` (it would leave the switch, not the loop) or a value repeats."""
    lines = text.split('\n')
    out, i = [], 0
    while i < len(lines):
        r = _chain(lines, i) if _IFCHAIN.match(lines[i]) else None
        if r and len(r[0]) >= minlen:
            arms, (rest, rind), end = r
            ind = len(_IFCHAIN.match(lines[i]).group(1))
            vals = [a[0] for a in arms]
            bodies = [b for _, b, _ in arms] + [rest]
            if len(set(int(x, 0) for x in vals)) == len(vals) and not any(re.match(r'^\s*break;$', x) for b in bodies for x in b):
                v = _IFCHAIN.match(lines[i]).group(2)
                out.append(' ' * ind + 'switch (%s) {' % v)
                for val, body, bind in arms + [(None, rest, rind)]:
                    if val is None and not any(x.strip() for x in body):
                        continue
                    out.append(' ' * ind + ('case %s:' % val if val is not None else 'default:'))
                    body = [x[bind - ind - 4:] if x.strip() else x for x in body]
                    out += body
                    last = next((x.strip() for x in reversed(body) if x.strip()), '')
                    if not re.match(r'^(return\b|goto\b)', last):
                        out.append(' ' * (ind + 4) + 'break;')
                out.append(' ' * ind + '}')
                i = end + 1
                continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)


_STK = re.compile(r'int stk\[(\d+)\];')
_STKUSE = re.compile(r'\(int\)stk \+ (\d+)')


def frame_rebase(text):
    """The generator writes a function's stack array one word below its first used slot: `int stk[16]` used from `(int)stk + 4`,
    so the compiler adds 4 to the frame pointer before every access and the original (the slot at the pointer itself) does not
    (Zombie Revenge: 1,154 of 1,282 such functions; FUN_0c0c0304 72 bytes to 66). Every `(int)stk + K` becomes `(int)stk + K-m`
    for the function's lowest K = m, and the array loses m/4 words. Left alone: a function that uses stk any other way
    (stk[i]), whose lowest offset is 0 or not a word multiple."""
    def one(m):
        body = m.group(2)
        d = _STK.search(body)
        if not d:
            return m.group(0)
        rest = body[:d.start()] + body[d.end():]
        uses = _STKUSE.findall(rest)
        if not uses or len(re.findall(r'\bstk\b', rest)) != len(uses):
            return m.group(0)
        lo = min(int(k) for k in uses)
        n = int(d.group(1))
        if lo == 0 or lo % 4 or n - lo // 4 < 1:
            return m.group(0)
        rest = _STKUSE.sub(lambda u: '(int)stk + %d' % (int(u.group(1)) - lo), rest)
        return m.group(1) + body[:d.start()] + 'int stk[%d];' % (n - lo // 4) + rest[d.start():] + m.group(3)
    return re.sub(r'(^\{\n)(.*?)(\n\}$)', one, text, flags=re.M | re.S)


_BUILTIN = re.compile(r'_builtin_(sqrtf|fabsf)\((\w+)\)')
_DECL = re.compile(r'^\s+(?:register )?(?:unsigned )?(?:int|float|short|char)\s+[\w\[\], ]+;$')


def hoist_builtins(text):
    """A pure builtin called with the same variable more than once, once per comparison (Zombie Revenge FUN_0c0341a6: three
    `_builtin_sqrtf(u5)` where the original takes the root once and compares three times; 242 extra evaluations in 96
    functions), is computed once into a new local before the first call and read from there. Only when the argument is a plain
    variable that is not assigned at or after the first call and never has its address taken, every call lies in the block of the
    first (no line between them is indented less), and the function has no loop, goto or label: then the value is the same at
    every call, and computing it early is harmless (the builtin has no side effect)."""
    def one(m):
        lines = m.group(2).split('\n')
        if any(re.search(r'\b(for|while|do|goto)\b', l) or re.match(r'^\s*\w+:;?\s*$', l) for l in lines):
            return m.group(0)
        n = 0
        while True:
            hit = None
            seen = {}
            for i, l in enumerate(lines):
                for c in _BUILTIN.finditer(l):
                    seen.setdefault((c.group(1), c.group(2)), []).append(i)
            for (fn_, arg), at in sorted(seen.items(), key=lambda kv: kv[1][0]):
                if len(at) < 2 or arg[0].isdigit() or any('&' + arg in l for l in lines):
                    continue
                first, last = at[0], at[-1]
                ind = len(lines[first]) - len(lines[first].lstrip())
                if any(re.search(r'(?<![\w.])%s\s*=(?!=)' % re.escape(arg), l) for l in lines[first:]):
                    continue
                if any(l.strip() and len(l) - len(l.lstrip()) < ind for l in lines[first:last + 1]):
                    continue
                hit = (fn_, arg, first)
                break
            if not hit:
                break
            fn_, arg, first = hit
            n += 1
            name = 's%d' % n
            while any(re.search(r'\b%s\b' % name, l) for l in lines):
                n += 1
                name = 's%d' % n
            call = '_builtin_%s(%s)' % (fn_, arg)
            ind = ' ' * (len(lines[first]) - len(lines[first].lstrip()))
            for i in range(first, len(lines)):
                lines[i] = lines[i].replace(call, name)
            lines.insert(first, '%s%s = %s;' % (ind, name, call))
            d = 0
            while d < len(lines) and (_DECL.match(lines[d]) or not lines[d].strip()):
                d += 1
            while d > 0 and not lines[d - 1].strip():
                d -= 1
            lines.insert(d, '    float %s;' % name)
        return m.group(1) + '\n'.join(lines) + m.group(3)
    return re.sub(r'(^\{\n)(.*?)(\n\}$)', one, text, flags=re.M | re.S)


_BARE_STK = re.compile(r'^\s*\*\(volatile (?:unsigned )?(?:int|short|char|float) \*\)\(\(int\)stk \+ \d+\);$')
_DEAD_STORE = re.compile(r'^\s*\*\((?:unsigned )?(?:int|short|char|float) \*\)\(\(?\(int\)stk \+ \d+\)\)? = ([^;]*);$')


def drop_dead_frame(text):
    """A function whose stack array nothing reads. The generator keeps register shuffles in `stk` slots and ends some functions with a
    bare `*(volatile int *)((int)stk + 4);` (the load of a restored register); when no slot is ever read and the array's address
    goes nowhere, the compiler still builds a frame, keeps a frame-pointer copy and writes the slots (Zombie Revenge FUN_0c0b1800:
    the original has no frame, the C a 12-byte one). The stores, the bare reads and the array go: 42 functions, 4.3 KB of excess.
    Left alone: any other use of stk, and a store whose value is a call or a volatile read (it has an effect)."""
    def one(m):
        lines = m.group(2).split('\n')
        di = next((i for i, l in enumerate(lines) if re.match(r'^\s*int stk\[\d+\];$', l)), None)
        if di is None:
            return m.group(0)
        keep = []
        dropped = 0
        for i, l in enumerate(lines):
            if i == di:
                continue
            sm = _DEAD_STORE.match(l)
            if _BARE_STK.match(l) or (sm and 'stk' not in sm.group(1) and 'volatile' not in sm.group(1) and not re.search(r'\w\(', sm.group(1))):
                dropped += 1
                continue
            keep.append(l)
        if any('stk' in l for l in keep):
            return m.group(0)
        while keep and keep[0] == '' and len(keep) > 1 and keep[1] == '':
            keep.pop(0)
        return m.group(1) + '\n'.join(keep) + m.group(3)
    return re.sub(r'(^\{\n)(.*?)(\n\}$)', one, text, flags=re.M | re.S)


def function_names(text):
    """The names of the functions a unit's text defines."""
    return re.findall(r'^[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;{]*\)\s*\n\{', text, re.M)


def by_function_size(unit_funcs, size, least):
    """The units of {unit: [function]} that hold a function of at least `least` bytes (size: {function: bytes}), the one with the
    largest such function first; ties by name. A unit with none is left out."""
    best = {u: max((size.get(n, 0) for n in names), default=0) for u, names in unit_funcs.items()}
    return sorted((u for u in best if best[u] >= least), key=lambda u: (-best[u], u))


_VDEF = re.compile(r'^(?P<type>int|unsigned int|float|short|char|unsigned char|double)\s+(?P<name>\w+)\s*\((?P<params>[^;{]*)\)\s*\n\{', re.M)
_CALLNAME = re.compile(r'\b([A-Za-z_]\w*)\s*\(')
_DECLPREFIX = re.compile(r'^\s*(?:extern\s+)?(?:unsigned\s+)?(?:int|float|void|short|char|double)\s+\**\s*$')


def unused_value_names(texts, reg_of):
    """{names} of the functions the given unit texts ({file: text}) define, that the original returns no register for (reg_of(name) is
    None: retcheck found no write to r0 or fr0 before its rts, or the paths disagree) and whose value no call reads: a call that is
    a statement of its own, a declaration or the definition line is not a use; an assignment, a condition, an argument or a return
    of it is. These can be written `void` (void_returns): the C proves either way, since equiv.py compares r0 only for a C that
    returns a value, so what decides is whether a caller reads it."""
    defined = set()
    used = set()
    for t in texts.values():
        defined.update(m.group('name') for m in _VDEF.finditer(t))
        for m in _CALLNAME.finditer(t):          # one pass over the text: every name followed by `(` whose line has something before it
            prefix = t[t.rfind('\n', 0, m.start()) + 1:m.start()]
            if prefix.strip() and not _DECLPREFIX.match(prefix):
                used.add(m.group(1))
    return {n for n in defined if n not in used and reg_of(n) is None}


def _groups(expr):
    """The top-level pieces of an expression: [(kind, text)], kind 'g' for a parenthesised group and 't' for anything else."""
    out, d, cur, kind = [], 0, '', 't'
    for ch in expr:
        if ch == '(':
            if d == 0 and cur:
                out.append((kind, cur))
                cur = ''
            d += 1
            kind = 'g'
        cur += ch
        if ch == ')':
            d -= 1
            if d == 0:
                out.append(('g', cur))
                cur, kind = '', 't'
    if cur:
        out.append((kind, cur))
    return out


def _pure_call(expr):
    """True when the whole expression is one call: `name(args)` or `((type)(name))(args)`."""
    g = _groups(expr.strip())
    if len(g) == 2 and g[1][0] == 'g' and ((g[0][0] == 't' and re.match(r'^\w+$', g[0][1])) or g[0][0] == 'g'):
        return True
    return False


def void_returns(text, names):
    """The functions in names written `void`: the type of the definition and of its prototypes in this text, `return value;` as
    `return;`, `return call(args);` as the call and `return;`. A function with a `return` that is not alone on its line, a value that
    holds a call inside an expression, or a pointer or void type is left whole (a half-converted function does not compile)."""
    out = []
    for m in _VDEF.finditer(text):
        n = m.group('name')
        if n not in names:
            continue
        end = text.find('\n}\n', m.end())
        if end < 0:
            continue
        body = text[m.end():end]
        new = []
        ok = True
        for line in body.split('\n'):
            if not re.search(r'\breturn\b', line):
                new.append(line)
                continue
            mm = re.match(r'^(\s*)return\s*(.*?);\s*$', line)
            if not mm:
                ok = False
                break
            ind, expr = mm.groups()
            if not expr:
                new.append(line)
            elif re.search(r'[\w\)]\s*\(', expr):
                if not _pure_call(expr):
                    ok = False
                    break
                new += [ind + expr + ';', ind + 'return;']
            else:
                new.append(ind + 'return;')
        if not ok:
            continue
        head = 'void %s(%s)\n{' % (n, m.group('params'))
        out.append((m.start(), end, head + '\n'.join(new)))
    if not out:
        return text
    res, pos = [], 0
    for a, b, rep in out:
        res.append(text[pos:a])
        res.append(rep)
        pos = b
    res.append(text[pos:])
    got = ''.join(res)
    for n in [m.group('name') for m in _VDEF.finditer(text) if m.group('name') in names]:
        got = re.sub(r'(?m)^((?:extern\s+)?)(?:int|unsigned int|float|short|char|unsigned char|double)(\s+%s\s*\([^;{]*\);)$' % re.escape(n), r'\1void\2', got)
    return got


# The generator's last passes on a function's C, in order: (shrink.py pass name, the GEN_<NAME> switch that turns it off with 0, the
# rewrite). gen_drv.build applies them to every function it writes, so new C is born small; shrink.py --passes runs the same rewrites
# on C written before. rebase is last: the other passes read the stack array's old offsets.
LAST_PASSES = [
    ('selfcopy', 'GEN_SELFCOPY', drop_self_copies),         # frame slots stored back unchanged
    ('smod', 'GEN_SMOD', fold_signed_mask),                 # the sign sequence of a signed remainder by 2^k as one `%` line
    ('struct', 'GEN_STRUCT', struct_access),                # far field accesses as members (head_protos declares the structures)
    ('globase', 'GEN_GLOBASE', global_base),                # nearby fixed addresses off one base
    ('switch', 'GEN_SWITCH', chains_to_switch),             # a state chain of ifs as a switch
    ('copies', 'GEN_COPIES', merge_copies),                 # a result threaded through nesting levels by copies
    ('deadframe', 'GEN_DEADFRAME', drop_dead_frame),        # a stack array nothing reads goes (after the self-copies are gone)
    ('hoist', 'GEN_HOIST', hoist_builtins),                 # a pure builtin called more than once with the same variable: once
    ('rebase', 'GEN_REBASE', frame_rebase),                 # the stack array based at its first used word
]


def last_passes(text):
    """text through every LAST_PASSES rewrite whose GEN_<NAME> switch is not 0."""
    import os
    for _name, env, fn in LAST_PASSES:
        if os.environ.get(env, '1') != '0':
            text = fn(text)
    return text
