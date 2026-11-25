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
        # a comment right above the first definition (a /* manual: */ line) belongs to it: the declarations go before the comment
        m = re.search(r'(?:\n|^)(/\*(?:[^*]|\*(?!/))*\*/\s*)$', head)
        cut = m.start(1) if m else len(head)
        text = head[:cut].rstrip('\n') + '\n' + '\n'.join(add) + '\n' + ('\n' + head[cut:] if m else '') + text[len(head):]
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
_IMASK = re.compile(r'_builtin_set_imask\(\(\(unsigned int\)\(\(\(')


def fold_imask(text):
    """`_builtin_set_imask(((unsigned int)(((X & 0xF) << 2) << 2) >> 4));` as `_builtin_set_imask(X);`. The generator reads the mask
    back from the SR arithmetic and writes that arithmetic into the argument, but the builtin itself masks with 15 and shifts
    (`and #15; shll2; shll2` in its own code), so the compiler emitted both twice: 10 bytes a use."""
    out, pos = [], 0
    for m in _IMASK.finditer(text):
        if m.start() < pos:
            continue
        i = m.end()                      # X starts here; find the `&` that closes it at depth 0
        depth, k = 0, i
        while k < len(text) and text[k] != '\n':
            ch = text[k]
            if ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    break
                depth -= 1
            elif ch == '&' and depth == 0:
                break
            k += 1
        tail = ' & 0xF) << 2) << 2) >> 4))'
        if k < len(text) and text[k - 1:k + len(tail) - 1] == tail and text[k + len(tail) - 1:k + len(tail)] == ';':
            out.append(text[pos:m.start()] + '_builtin_set_imask(' + text[i:k - 1] + ')')
            pos = k + len(tail) - 1
    return ''.join(out) + text[pos:]


_FNHEAD = re.compile(r'^(?:static )?((?:unsigned |signed )?\w+)\s+\**\w+\([^;{}]*\)\s*$')
_RETV = re.compile(r'^    return \(?(t\d+)\)?;$')
_IFOPEN = re.compile(r'^(\s*)if \(.*\) \{$')
_ELSE = re.compile(r'^(\s*)\} else (?:if \(.*\) )?\{$')


def early_returns(text):
    """`tR = E;` as the last statement of an if arm, with nothing between the end of that if and the function's `return tR;`, as
    `return E;`. The structured form carries the result in one temporary to a single return, assigned at the end of each arm of
    its nested ifs; the compiler keeps it alive through the nest, where the source returned at each test (66, 30, 6 and 6 bytes in
    four library functions). Only ifs in tail position: an arm of a loop or a switch, or an if followed by any statement or label,
    is left alone, and so is a temporary whose declared type is not the function's return type (`return E` would then convert
    differently)."""
    lines = text.split('\n')
    k = 0
    while k < len(lines):
        m = _FNHEAD.match(lines[k])
        if not (m and k + 1 < len(lines) and lines[k + 1] == '{'):
            k += 1
            continue
        end = next((q for q in range(k + 2, len(lines)) if lines[q] == '}'), None)
        if end is None:
            break
        rtype = m.group(1)
        mr = _RETV.match(lines[end - 1]) if end - 1 > k + 1 else None
        if mr and rtype != 'void':
            v = mr.group(1)
            decl = next((x for x in lines[k + 2:end] if re.match(r'^\s*(?:register )?[\w ]+\b%s;$' % v, x)), None)
            dtype = re.sub(r'^register ', '', decl.strip())[:-len(v) - 1].strip() if decl else None
            if dtype == rtype:
                _tail_returns(lines, end - 2, k + 2, v)
        k = end + 1
    return '\n'.join(lines)


def _tail_returns(lines, j, lo, v):
    """The statement ending at line j is the last before the result is returned: when it is an if (with its else arms), the last
    statement of each arm is too."""
    x = lines[j]
    ind = len(x) - len(x.lstrip())
    if x.strip() != '}':
        return
    starts = []                           # the opening line of each arm, the last arm first
    q = j
    while True:
        q -= 1
        while q >= lo and not (lines[q].strip() and len(lines[q]) - len(lines[q].lstrip()) == ind):
            q -= 1
        if q < lo:
            return
        if _ELSE.match(lines[q]):
            starts.append(q)
            continue
        if _IFOPEN.match(lines[q]):
            starts.append(q)
            break
        return                            # a loop, a switch, a bare block: not an if chain
    ends = [j] + starts[:-1]              # the line closing each arm
    for s, e in zip(starts, ends):
        last = next((z for z in range(e - 1, s, -1) if lines[z].strip()), None)
        if last is None:
            continue
        ma = re.match(r'^(\s*)%s = (.*);$' % v, lines[last])
        if ma and len(ma.group(1)) == ind + 4:
            lines[last] = '%sreturn %s;' % (ma.group(1), ma.group(2))
        elif lines[last].strip() == '}' and len(lines[last]) - len(lines[last].lstrip()) == ind + 4:
            _tail_returns(lines, last, s + 1, v)


_SCALARDECL = re.compile(r'^    (?:register )?(?:unsigned )?(?:int|float|short|char) ?\*?(\w+);$')


def drop_unused_locals(text):
    """A scalar local that is declared and named nowhere else in its function is not declared. The generator declares a variable for
    every register it tracked, also the ones no statement ends up naming, and declares them `register`; in a large function the
    compiler lets them take part in handing out its saved registers (one function 7,144 to 5,434 bytes for 11 such lines). A
    declaration with an initialiser, an array and a structure are left alone."""
    lines = text.split('\n')
    out, k = [], 0
    while k < len(lines):
        if not (_FNHEAD.match(lines[k]) and k + 1 < len(lines) and lines[k + 1] == '{'):
            out.append(lines[k])
            k += 1
            continue
        end = next((q for q in range(k + 2, len(lines)) if lines[q] == '}'), None)
        if end is None:
            out.extend(lines[k:])
            break
        body = lines[k:end + 1]
        text_ = '\n'.join(body)
        keep = []
        for l in body:
            m = _SCALARDECL.match(l)
            if m and len(re.findall(r'\b%s\b' % re.escape(m.group(1)), text_)) == 1:
                continue
            keep.append(l)
        out.extend(keep)
        k = end + 1
    return '\n'.join(out)


_REGDECL = re.compile(r'^    register (?:unsigned )?(?:int|float|short|char) ?\*?(\w+);$')


def order_registers(text):
    """The `register` declarations of each function, most-named variable first (the lines stay where such declarations were, equal
    counts keep their order, one with an initialiser is not moved). SHC gives its saved registers to `register` variables in the
    order they are declared and keeps the rest in the frame; the generator declares temporaries in the order it made them, so the
    ones a loop names most often could be the ones in memory. The order of declarations without initialisers changes nothing in
    what the C does."""
    lines = text.split('\n')
    k = 0
    while k < len(lines):
        if not (_FNHEAD.match(lines[k]) and k + 1 < len(lines) and lines[k + 1] == '{'):
            k += 1
            continue
        end = next((q for q in range(k + 2, len(lines)) if lines[q] == '}'), None)
        if end is None:
            break
        idx = [i for i in range(k + 2, end) if _REGDECL.match(lines[i])]
        if len(idx) >= 2:
            body = '\n'.join(lines[k + 2:end])
            count = {i: len(re.findall(r'\b%s\b' % re.escape(_REGDECL.match(lines[i]).group(1)), body)) for i in idx}
            order = sorted(idx, key=lambda i: -count[i])
            moved = [lines[i] for i in order]
            for i, d in zip(idx, moved):
                lines[i] = d
        k = end + 1
    return '\n'.join(lines)


_PUSHST = re.compile(r'^\s*\*\((?:unsigned )?int \*\)\(+\(int\)stk \+ (\d+)\)+ = (.+);$')
_CALLLN = re.compile(r'^\s*(?:return |\w+ = )?(\w+)\(')


def _call_args(line):
    """The top-level arguments of the named call on this line, or None."""
    m = _CALLLN.match(line)
    if not m:
        return None
    i = line.index('(', m.end(1))
    depth, out, cur = 0, [], ''
    for ch in line[i + 1:]:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    out.append(cur.strip())
    return out


_SLOTREF = re.compile(r'(\*\((?:unsigned |signed )?(?:int|short|char|float) ?\*?\)\(+)?\(int\)stk \+ (\d+)\)(?: \+ (0x[0-9A-Fa-f]+|\d+))?')
_PLAINSET = re.compile(r'^\s*(\w+) = ([^;]*);$')


def _stk_blocked(line, slots):
    """The stored slots (their offsets) that this line reads or can reach through an address. A direct load or store of the slot
    reaches the 4 bytes it is in; an address (no `*(T *)` in front, or one with an offset added) reaches every slot at or above it.
    A use of `stk` in any form this does not know blocks all of them."""
    cut = _SLOTREF.sub('', line)
    if re.search(r'\bstk\b(?!\s*\[)', cut) or re.search(r'\(int\)stk \+ \d+ \+', line) or re.search(r'\(int\)stk \+ \d+\) \+ \w+ \+', line):
        return set(slots)
    out = set()
    for m in _SLOTREF.finditer(line):
        base, add = int(m.group(2)), (int(m.group(3), 0) if m.group(3) else 0)
        if m.group(1) and not m.group(3):
            out |= {s for s in slots if s <= base < s + 4}
        else:
            out |= {s for s in slots if s + 4 > base + add}
    return out


def drop_pushed_stores(text):
    """A store into the frame array whose value is one of the next call's arguments past the fourth, with nothing between them but
    plain assignments that leave the value alone, is not written when nothing else reads or can reach its slot. The generator
    writes the words a caller pushes twice, as stores into the frame and as the call's own arguments; the compiler then pushes them
    and stores them as well (5.7 bytes a store over 143 functions of a studio's game). Direct loads of the slot, addresses that
    reach it, and any use of `stk` in a form not known here keep the store."""
    lines = text.split('\n')
    k = 0
    while k < len(lines):
        if not (_FNHEAD.match(lines[k]) and k + 1 < len(lines) and lines[k + 1] == '{'):
            k += 1
            continue
        end = next((q for q in range(k + 2, len(lines)) if lines[q] == '}'), None)
        if end is None:
            break
        cand = []                                     # (line, slot) of a store the next call carries
        for j in range(k + 2, end):
            m = _PUSHST.match(lines[j])
            if not m:
                continue
            e = m.group(2).strip()
            names = set(re.findall(r'[A-Za-z_]\w*', e))
            for i in range(j + 1, end):
                a = _call_args(lines[i])
                if a is not None:
                    if len(a) >= 5 and e in a[4:]:
                        cand.append((j, int(m.group(1))))
                    break
                s = lines[i]
                if _PUSHST.match(s):
                    continue
                pm = _PLAINSET.match(s)
                if not pm or re.search(r'\b\w+\(', pm.group(2)) or pm.group(1) in names:
                    break
        if cand:
            slots = {s for _, s in cand}
            gone = {j for j, _ in cand}
            for q in range(k + 2, end):
                if q not in gone and 'stk' in lines[q] and not _PUSHST.match(lines[q]):
                    slots -= _stk_blocked(lines[q], slots)
                elif q not in gone and _PUSHST.match(lines[q]):
                    mm = _PUSHST.match(lines[q])
                    slots -= _stk_blocked(lines[q][lines[q].index('=') + 1:], slots)      # the stored value may read the slot
                    if int(mm.group(1)) in slots and (int(mm.group(1)), q) not in [(s, j) for j, s in cand]:
                        pass                          # a second store to the same slot: a different value; the slot is still never read
            for j, s in sorted(cand, reverse=True):
                if s in slots:
                    del lines[j]
                    end -= 1
        k = end + 1
    return '\n'.join(lines)


# ---- the "stack" passes: size rewrites of a function's C (shrink.py --passes rtfold,inlinetemps,...). Each takes one function's text
# (head line, `{`, body, `}`) and returns text; shrink.py keeps a function only when it compiles smaller and still proves. ----

_HEXV = r'0x[0-9A-Fa-f]+'
_TYPEWORDS = {'int', 'float', 'short', 'char', 'unsigned', 'signed', 'long', 'double', 'void', 'struct', 'volatile', 'register'}
_ASSIGN = re.compile(r'^\s*([A-Za-z_]\w*) (?:[-+*/|&^]|<<|>>)?= ')


def _close(s, i):
    """index of the `)` that closes the `(` at s[i], or -1"""
    d = 0
    for j in range(i, len(s)):
        if s[j] == '(':
            d += 1
        elif s[j] == ')':
            d -= 1
            if d == 0:
                return j
    return -1


def _wrapped(e):
    """e in parentheses of its own, unless it is a name, a literal or already one balanced group"""
    if re.fullmatch(r'\w+|-?0x[0-9A-Fa-f]+', e) or (e.startswith('(') and _close(e, 0) == len(e) - 1):
        return e
    return '(' + e + ')'


def _idents(e):
    return {w for w in re.findall(r'(?<![\w.])[A-Za-z_]\w*', e) if w not in _TYPEWORDS}


def _addr_taken(text, names):
    return any(re.search(r'&\s*%s\b' % re.escape(v), text) for v in names)


def fold_offsets(text):
    """`((x + 0x10) - 0x4)` as `(x + 0xC)`, `(x + 0x0)` as `x`, `((x + 0x4))` as `(x + 0x4)`: the offset arithmetic the generator leaves
    in two steps (constants only, one variable; the value is the same)."""
    pat = re.compile(r'\(\(([A-Za-z_]\w*) ([+-]) (%s)\) ([+-]) (%s)\)' % (_HEXV, _HEXV))

    def rep(m):
        k = int(m.group(3), 16) * (1 if m.group(2) == '+' else -1) + int(m.group(5), 16) * (1 if m.group(4) == '+' else -1)
        return '(%s %s 0x%X)' % (m.group(1), '+' if k >= 0 else '-', abs(k))
    while True:
        t2 = pat.sub(rep, text)
        t2 = re.sub(r'\(([A-Za-z_]\w*) [+-] 0x0\)', r'\1', t2)
        t2 = re.sub(r'\(\(([A-Za-z_]\w* [+-] %s)\) \+ 0x0\)' % _HEXV, r'(\1)', t2)
        t2 = re.sub(r'\(\(([A-Za-z_]\w* [+-] %s)\)\)' % _HEXV, r'(\1)', t2)
        if t2 == text:
            return text
        text = t2


def no_register(text):
    """`register int t0;` as `int t0;`: no variable asks for a saved register, the compiler chooses."""
    return re.sub(r'(?m)^(\s*)register ((?:int|float) )', r'\1\2', text)


def const_prop(text):
    """`t = 0xK;` and the uses of t in the straight-line statements that follow (up to a brace, a label, a goto or a new value of t) read
    the constant. A name whose address is taken, or that is changed in place (`t += 1`, `t++`), is left alone."""
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        m = re.match(r'^(\s*)([tu]\d+) = (0x[0-9A-Fa-f]+);$', lines[i])
        if m and not _addr_taken(text, [m.group(2)]):
            x, k = m.group(2), m.group(3)
            use = re.compile(r'\b%s\b' % x)
            inplace = re.compile(r'\b%s\s*(?:[-+*/|&^]|<<|>>)=|\+\+%s\b|--%s\b|\b%s(?:\+\+|--)' % ((x,) * 4))
            j = i + 1
            while j < len(lines):
                l = lines[j]
                if re.search(r'[{}]', l) and not use.search(l):
                    break
                if re.match(r'^\s*%s = ' % x, l):
                    r = l.split(' = ', 1)
                    if use.search(r[1]):
                        lines[j] = r[0] + ' = ' + use.sub(k, r[1])
                    break
                if use.search(l):
                    if re.search(r'[{}]', l) or re.search(r'\b%s = ' % x, l) or inplace.search(l):
                        break
                    lines[j] = use.sub(k, l)
                if re.search(r'[{}]|goto|^\s*\w+:', l):
                    break
                j += 1
        i += 1
    return '\n'.join(lines)


def merge_constants(text):
    """A temporary whose every assignment is the same literal (the original kept a constant in a register, the generator carries that
    register through each arm as a variable) is replaced by the literal, its assignments and declaration gone. An int takes an integer
    literal and a float a float literal only (the other would change the arithmetic); a name whose address is taken, or that is changed
    in place, stays."""
    lit_int = r'-?(?:0x[0-9A-Fa-f]+|\d+)'
    lit_flt = r'-?\d+(?:\.\d+)?(?:e[+-]?\d+)?f'
    for _ in range(20):
        changed = False
        decls = dict((m.group(2), m.group(1)) for m in re.finditer(r'(?m)^\s*(?:register )?(int|float) ([tu]\d+);', text))
        for x in sorted(decls):
            asg = re.findall(r'(?m)^\s*%s = (.*);$' % x, text)
            if not asg or len(re.findall(r'\b%s = ' % x, text)) != len(asg):
                continue
            vals = set(a.strip('()') for a in asg)
            lit = lit_int if decls[x] == 'int' else lit_flt
            if len(vals) != 1 or not re.fullmatch(lit, asg[0].strip('()')):
                continue
            rest = re.sub(r'(?m)^\s*%s = .*;$' % x, '', text)
            if re.search(r'&\s*%s\b|\b%s\s*(?:[-+*/|&^]|<<|>>)?= |\+\+%s|--%s|%s\+\+|%s--' % ((x,) * 6), rest):
                continue
            v = vals.pop()
            v = '(%s)' % v if v.startswith('-') else v
            text = re.sub(r'(?m)^\s*%s = .*;\n' % x, '', text)
            text = re.sub(r'(?m)^\s*(?:register )?(?:int|float) %s;\n' % x, '', text)
            text = re.sub(r'\b%s\b' % x, v, text)
            changed = True
        if not changed:
            break
    return text


def drop_outargs(text):
    """The stores into the frame array the generator writes for the words the original pushed for a call (`*(int *)((int)stk + 8) = v;`,
    beside the call's own arguments, which the compiler pushes again) are not written when nothing reads or can reach their slot (a
    direct load, an address, any use of `stk` in a form not known keeps the store) and the value has no call or volatile read."""
    lines = text.split('\n')
    k = 0
    while k < len(lines):
        if not (_FNHEAD.match(lines[k]) and k + 1 < len(lines) and lines[k + 1] == '{'):
            k += 1
            continue
        end = next((q for q in range(k + 2, len(lines)) if lines[q] == '}'), None)
        if end is None:
            break
        cand = []
        for j in range(k + 2, end):
            m = _PUSHST.match(lines[j])
            if m and not re.search(r'\w\(|volatile', m.group(2)):
                cand.append((j, int(m.group(1))))
        if cand:
            slots = {s for _, s in cand}
            gone = {j for j, _ in cand}
            for q in range(k + 2, end):
                if q in gone:
                    mm = _PUSHST.match(lines[q])
                    slots -= _stk_blocked(lines[q][lines[q].index('=') + 1:], slots)     # the stored value may read a slot
                elif 'stk' in lines[q]:
                    slots -= _stk_blocked(lines[q], slots)
            for j, s in sorted(cand, reverse=True):
                if s in slots:
                    del lines[j]
                    end -= 1
        k = end + 1
    return '\n'.join(lines)


def trim_stack_args(text):
    """A call through a pointer cast, `((int (*)(int, int, int, int, int))(fp))(a, b, c, d, *(int *)((int)stk + 8 + 4))`, that the
    generator hands the caller's own frame words after its register arguments: the call keeps the register arguments (at most four)
    and the cast type its first kinds."""
    out = []
    for l in text.split('\n'):
        m = re.search(r'\(\(int \(\*\)\(((?:int|float)(?:, (?:int|float))*)\)\)', l)
        if m and re.search(r'\*\(int \*\)\(\(int\)stk \+ \d+ \+ \d+\)', l):
            j = m.end()
            k = _close(l, j) if j < len(l) and l[j] == '(' else -1
            if k > 0:
                a0 = k + 1
                if l[a0:a0 + 1] == ')':
                    a0 += 1
                if l[a0:a0 + 1] == '(':
                    a1 = _close(l, a0)
                    if a1 > 0:
                        args, depth, cur = [], 0, ''
                        for ch in l[a0 + 1:a1]:
                            if ch == ',' and depth == 0:
                                args.append(cur.strip())
                                cur = ''
                            else:
                                depth += ch == '('
                                depth -= ch == ')'
                                cur += ch
                        args.append(cur.strip())
                        keep = []
                        for a in args:
                            if re.match(r'^\*\(int \*\)\(\(int\)stk \+ \d+( \+ \d+)?\)$', a) or (len(keep) >= 4 and re.match(r'^R\d+$', a)):
                                break
                            keep.append(a)
                        keep = keep[:4]
                        if keep and len(keep) < len(args):
                            tys = m.group(1).split(', ')[:len(keep)]
                            l = l[:m.start()] + '((int (*)(%s))' % ', '.join(tys) + l[m.end():a0] + '(' + ', '.join(keep) + ')' + l[a1 + 1:]
        out.append(l)
    return '\n'.join(out)


_MF_NAME = {'int': 'int', 'unsigned int': 'uint', 'float': 'float', 'short': 'short', 'unsigned short': 'ushort', 'char': 'char', 'unsigned char': 'uchar'}


def member_form(text):
    """`*(int *)((a4 + 0x38))` as `(((struct o38_int *)(a4))->v)` (struct_decls lists the declarations; shrink.py's splice writes them
    after the unit head): the member compiles as an addressing mode where a cast sum is arithmetic that SHC hoists into a slot of its
    own in a loop. The variable must be a plain name that is not declared a pointer or array, the offset a multiple of the type's size.
    The replacement is a whole parenthesised expression; the parentheses around the original are never touched."""
    head = text.split('{', 1)[0]
    scaled = set(re.findall(r'\*\s*(\w+)\s*[,)]', head)) | set(re.findall(r'^\s*(?:register )?[\w ]+?\*\s*(\w+);$', text, re.M)) \
        | set(re.findall(r'\b(\w+)\[\d*\];', text))
    pat = re.compile(r'\*\((unsigned int|int|float|short|unsigned short|char|unsigned char) \*\)\(')
    out, i = [], 0
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            break
        o = m.end() - 1
        c = _close(text, o)
        if c < 0:
            out.append(text[i:])
            break
        inner = text[o + 1:c]
        while inner.startswith('(') and _close(inner, 0) == len(inner) - 1:
            inner = inner[1:-1]
        mm = re.fullmatch(r'([A-Za-z_]\w*) \+ (%s)' % _HEXV, inner)
        ty = m.group(1)
        if mm:
            k = int(mm.group(2), 16)
        if not mm or mm.group(1) in scaled or mm.group(1) == 'stk' or k == 0 or k >= 0x10000 or k % _TSIZE.get(ty, 1):
            out.append(text[i:o + 1])
            i = o + 1
            continue
        out.append(text[i:m.start()])
        out.append('(((struct o%X_%s *)(%s))->v)' % (k, _MF_NAME[ty], mm.group(1)))
        i = c + 1
    return ''.join(out)


def mul_once(text, minuses=3):
    """`(t5 * 0x38)` written at three or more places, t5 a temporary assigned by one statement (and not before its first use, its
    address never taken): computed once, after that assignment."""
    for n in range(6):
        cnt = {}
        for m in re.finditer(r'\(([tu]\d+) \* (%s)\)' % _HEXV, text):
            cnt[m.group(0)] = cnt.get(m.group(0), 0) + 1
        done = False
        for e, k in sorted(cnt.items(), key=lambda x: -x[1]):
            if k < minuses:
                break
            x = re.match(r'\(([tu]\d+)', e).group(1)
            asg = list(re.finditer(r'(?m)^([ \t]*)%s = .*;$' % x, text))
            if len(asg) != 1 or len(re.findall(r'\b%s = ' % x, text)) != 1 or _addr_taken(text, [x]) or text.find(e) < asg[0].end():
                continue
            q = 'qm%d' % n
            a = asg[0]
            text = text[:a.end()] + '\n%s%s = %s;' % (a.group(1), q, e) + text[a.end():].replace(e, q)
            text = text.replace('\n{\n', '\n{\n    register int %s;\n' % q, 1)
            done = True
            break
        if not done:
            break
    return text


def address_registers(text, minuses=6, most=2):
    """A fixed address dereferenced at six or more places is held in a `register` variable set once at the top (the original keeps such
    addresses in saved registers; the C loads the pool word at each use)."""
    cnt = {}
    for m in re.finditer(r'\*\((?:unsigned int|int|float|short|unsigned short|signed char|unsigned char|char) \*\)(0x[0-9A-Fa-f]{6,8})\b', text):
        cnt[m.group(1)] = cnt.get(m.group(1), 0) + 1
    pick = [a for a, k in sorted(cnt.items(), key=lambda x: -x[1]) if k >= minuses][:most]
    if not pick or '\n{\n' not in text:
        return text
    lines = text.split('\n')
    i0 = lines.index('{') + 1
    i = i0
    while i < len(lines) and (re.match(r'^    (register )?(int|float)[ \*]+\w+(\[\d+\])?;$', lines[i]) or not lines[i].strip()):
        i += 1
    for k, a in enumerate(pick):
        lines.insert(i, '    qa%d = %s;' % (k, a))
    for k, a in enumerate(pick):
        lines.insert(i0, '    register int qa%d;' % k)
    t = '\n'.join(lines)
    for k, a in enumerate(pick):
        t = re.sub(r'(\*\((?:unsigned int|int|float|short|unsigned short|signed char|unsigned char|char) \*\))%s\b' % a, r'\1qa%d' % k, t)
    return t


def order_frame(text, ki=7, kf=4):
    """The ki most-named int and kf most-named float temporaries keep `register` and are declared first; every other local is declared
    plain, least-named first, so the most-named of those come last: SHC lays the frame out in declaration order from the top, and a slot
    within 60 bytes of r15 is one instruction where a farther one is two and a pool word."""
    m = re.search(r'(?m)^\{\n', text)
    if not m:
        return text
    body = text[m.end():]
    lines = body.split('\n')
    D = re.compile(r'^    (?:register )?(int \*|int |float )(\w+);$')
    idx = [i for i, l in enumerate(lines) if D.match(l)]
    if len(idx) < 2:
        return text

    def uses(v):
        return len(re.findall(r'\b%s\b' % re.escape(v), body)) - 1
    ds = [(D.match(lines[i]).group(1), D.match(lines[i]).group(2)) for i in idx]
    ds.sort(key=lambda d: -uses(d[1]))
    regs, rest, ci, cf = [], [], 0, 0
    for ty, v in ds:
        isf = ty.startswith('float')
        if ((isf and cf < kf) or (not isf and ci < ki)) and not re.search(r'&%s\b' % v, body):
            regs.append('    register %s%s;' % (ty, v))
            if isf:
                cf += 1
            else:
                ci += 1
        else:
            rest.append('    %s%s;' % (ty, v))
    new = regs + rest[::-1]
    for i, d in zip(idx, new):
        lines[i] = d
    return text[:m.end()] + '\n'.join(lines)


def _purecalls(s):
    s = re.sub(r'\((?:unsigned |signed )?(?:int|float|short|char|struct \w+|volatile [\w ]+) ?\**\)', '', s)
    return bool(re.search(r'[A-Za-z_]\w*\s*\(', s))


_BRACE_ETC = re.compile(r'[{}]|goto|^\s*\w+:|\bbreak;|\bcontinue;|\breturn\b')


def rt_fold(text):
    """Inside a straight-line run, a value assigned to a temporary that the same run assigns again (so it is dead after its uses between)
    is written into those uses: always for a copy or a constant, otherwise when it is read once and nothing in between stores, calls,
    or changes its operands (any variable, not only temporaries; a name whose address is taken is left). Folds the
    one-statement-per-instruction form of a loop body (`t5 = t1; t5 = (t5 << 1); t5 = (t5 + t1);`) back into expressions."""
    SIMPLE = re.compile(r'^(\s*)([tu]\d+) = (.*);$')
    for _ in range(8):
        lines = text.split('\n')
        changed = 0
        i = 0
        while i < len(lines):
            m = SIMPLE.match(lines[i])
            if not m:
                i += 1
                continue
            x, e = m.group(2), m.group(3)
            evars = _idents(e)
            if _purecalls(e) or _addr_taken(text, evars | {x}):
                i += 1
                continue
            trivial = bool(re.fullmatch(r'\(?(?:[tu]\d+|a\d|f\d+|-?0x[0-9A-Fa-f]+|-?\d+(?:\.\d+)?f?)\)?', e))
            hasload = bool(re.search(r'\*\(|->|\[', e))
            uses, j, ok, killed = [], i + 1, True, False
            while j < len(lines):
                l = lines[j]
                if not l.strip():
                    j += 1
                    continue
                if _BRACE_ETC.search(l):
                    break
                mm = SIMPLE.match(l)
                am = _ASSIGN.match(l)
                nuse = len(re.findall(r'\b%s\b' % x, l.split(' = ', 1)[1] if mm and mm.group(2) == x else l))
                if mm and mm.group(2) == x:
                    if nuse:
                        uses.append((j, nuse))
                    killed = True
                    break
                if nuse:
                    uses.append((j, nuse))
                stop = (am and am.group(1) in evars) or (hasload and (not mm or _purecalls(l)) and not trivial)
                if stop:
                    j += 1
                    while j < len(lines):         # scan on only to find the kill; any further use blocks the fold
                        l2 = lines[j]
                        if _BRACE_ETC.search(l2):
                            break
                        m2 = SIMPLE.match(l2)
                        if re.search(r'\b%s\b' % x, l2.split(' = ', 1)[1] if m2 and m2.group(2) == x else l2):
                            ok = False
                            break
                        if m2 and m2.group(2) == x:
                            killed = True
                            break
                        j += 1
                    break
                j += 1
            n = sum(k for _, k in uses)
            if killed and ok and (n == 0 or trivial or n == 1):
                ee = _wrapped(e)
                for j2, _k in uses:
                    l = lines[j2]
                    mm = SIMPLE.match(l)
                    if mm and mm.group(2) == x:
                        h, r = l.split(' = ', 1)
                        lines[j2] = h + ' = ' + re.sub(r'\b%s\b' % x, lambda _m: ee, r)
                    else:
                        lines[j2] = re.sub(r'\b%s\b' % x, lambda _m: ee, l)
                del lines[i]
                changed += 1
                continue
            i += 1
        text = '\n'.join(lines)
        if not changed:
            break
    return text


_ITSTORE = re.compile(r'^\s*(?:\*\(|\(\(\(struct |\(\*\(|g[0-9A-F]+ = |s\d+ = )')
_ITCHEAP = re.compile(r'^\(?\*\((?:unsigned int|int|float|short|unsigned short|signed char|unsigned char|char) \*\)\(*(?:0x[0-9A-Fa-f]+|\(int\)stk \+ \d+)\)*\)?$|^\(?(?:0x[0-9A-Fa-f]+|g[0-9A-F]+|s\d+)\)?$')


def inline_temps(text, multi=True):
    """A temporary set once and read only in the straight-line statements that follow (before any store, call, label or brace, and
    before anything changes its operands) is written into its use(s): once-read ones always, several-times-read ones when the value is
    a plain load of a fixed address or frame word, or a constant. The generator names every intermediate value; in a function too big
    for SHC to keep locals in registers each name is a frame slot with a store and a load."""
    for _ in range(6):
        lines = text.split('\n')
        starts = [i for i, l in enumerate(lines) if l == '{']
        if not starts:
            return text
        body_start = starts[0]
        changed = 0
        cnt, asg = {}, {}
        for l in lines[body_start:]:
            for v in re.findall(r'\b[tu]\d+\b', l):
                cnt[v] = cnt.get(v, 0) + 1
            for v in re.findall(r'\b([tu]\d+) = ', l):
                asg[v] = asg.get(v, 0) + 1
            for v in re.findall(r'&([tu]\d+)\b', l):
                asg[v] = 99
        dead = set()
        i = body_start
        while i < len(lines):
            m = lines[i] is not None and re.match(r'^(\s*)([tu]\d+) = (.*);$', lines[i])
            if m and asg.get(m.group(2)) == 1 and not re.search(r'\b%s\b' % m.group(2), m.group(3)):
                x, e = m.group(2), m.group(3)
                nuse = cnt[x] - 2          # the declaration and the assignment
                evars = _idents(e)
                if nuse >= 1 and not _purecalls(e) and not _addr_taken(text, evars):
                    cheap = bool(_ITCHEAP.match(e))
                    if nuse == 1 or (multi and cheap):
                        found, j, idx = 0, i + 1, []
                        while j < len(lines) and found < nuse:
                            l = lines[j]
                            if l is None:
                                j += 1
                                continue
                            if re.search(r'\b%s\b' % x, l):
                                idx.append(j)
                                found += len(re.findall(r'\b%s\b' % x, l))
                                if re.search(r'[{}]', l) and found < nuse:
                                    break
                            if found >= nuse:
                                break
                            if _BRACE_ETC.search(l):
                                break
                            if _ITSTORE.match(l) or _purecalls(l):
                                break
                            am = _ASSIGN.match(l)
                            if am and am.group(1) in evars:
                                break
                            j += 1
                        if found == nuse and idx:
                            ee = _wrapped(e)
                            for j2 in idx:
                                lines[j2] = re.sub(r'\b%s\b' % x, lambda _m: ee, lines[j2])
                            lines[i] = None
                            dead.add(x)
                            changed += 1
            i += 1
        if not changed:
            break
        lines = [l for l in lines if l is not None and not (re.match(r'^    (?:register )?(?:int|float) ([tu]\d+);$', l)
                                                           and re.match(r'^    (?:register )?(?:int|float) ([tu]\d+);$', l).group(1) in dead)]
        text = '\n'.join(lines)
    return text


_STKDIRECT = re.compile(r'\*\((unsigned int|int|float) \*\)\(\(int\)stk \+ (\d+)\)')


def stack_locals(text):
    """Each word of the frame array `stk[]` reached at a constant offset becomes a local of its own. Only when every use of `stk` is a
    direct load or store of one whole 4-byte word inside the array (`*(int *)((int)stk + 8)`, the offset a sum of constants): if an
    address of any slot is taken, passed on or stepped from (`(int)stk + 16` without a dereference, a struct copy, a short or char
    access, a volatile read, an index, any other use of `stk`), the function is left as it is, because the callee or the stepping
    reaches the neighbouring slots and locals are not neighbours. A slot read and written as different 4-byte types keeps the type
    most used and reads the others through a pointer cast of its own address."""
    t = const_prop(text)
    for _ in range(4):
        t = re.sub(r'\(\(\(int\)stk \+ (\d+)\) \+ (%s)\)' % _HEXV, lambda m: '((int)stk + %d)' % (int(m.group(1)) + int(m.group(2), 16)), t)
        t = re.sub(r'\(\(int\)stk \+ (\d+) \+ (\d+)\)', lambda m: '((int)stk + %d)' % (int(m.group(1)) + int(m.group(2))), t)
        t = re.sub(r'\(\(\(int\)stk \+ (\d+)\)\)', r'((int)stk + \1)', t)
    d = re.search(r'(?m)^    int stk\[(\d+)\];\n', t)
    if not d:
        return text
    probe = _STKDIRECT.sub('', t[:d.start()] + t[d.end():])
    if re.search(r'\bstk\b', probe):
        return text
    size = int(d.group(1)) * 4
    uses = {}
    for m in _STKDIRECT.finditer(t):
        n = int(m.group(2))
        if n % 4 or n + 4 > size:
            return text
        uses.setdefault(n, {})
        uses[n][m.group(1)] = uses[n].get(m.group(1), 0) + 1
    if not uses:
        return text
    kind = {n: max(sorted(u), key=lambda ty: u[ty]) for n, u in uses.items()}

    def rep(m):
        n = int(m.group(2))
        return 's%d' % n if m.group(1) == kind[n] else '(*(%s *)&s%d)' % (m.group(1), n)
    t = _STKDIRECT.sub(rep, t)
    decl = '\n'.join('    %s s%d;' % (kind[n], n) for n in sorted(kind)) + '\n'
    return t[:d.start()] + decl + t[d.end():]


def _scalar_names(text, head_end):
    """the scalar parameters and locals a function declares"""
    names = set()
    h = text[:head_end]
    p = h[h.find('(') + 1:h.rfind(')')]
    for a in p.split(','):
        w = re.findall(r'[A-Za-z_]\w*', a)
        if w and '*' not in a:
            names.add(w[-1])
    for m in re.finditer(r'(?m)^[ \t]+(?:register )?(?:unsigned |signed )?(?:int|float|short|char)\s+(\w+);$', text[head_end:]):
        names.add(m.group(1))
    return names


def cse_expr(text, minuses=2, minlen=30, rounds=40):
    """A pure expression (local variables, parameters, constants, arithmetic and casts to scalars; no load, call, comma or function
    name) written out at two or more places becomes one local, set just before the first statement that uses it. Safe only when that
    statement dominates every use (the block it is in stays open up to the last use and no label lies between), no operand is assigned
    from that statement to the end of the function and none has its address taken. An occurrence that is a call's argument list (after
    a name or a `)` that is not a scalar cast) is not one; a condition's own parentheses stay: `if ((a > 0))`."""
    m = re.search(r'(?m)^\{\n', text)
    if not m:
        return text
    head, body = text[:m.end()], text[m.end():]
    n = 0
    CAST = re.compile(r'\((?:unsigned |signed )?(?:int|float|short|char) ?\**\)$')

    def occurrences(l, e):
        out, p = [], l.find(e)
        while p >= 0:
            prev = l[:p]
            if not prev or not (prev[-1].isalnum() or prev[-1] in '_)') or CAST.search(prev) \
                    or prev.endswith(('if ', 'while ', 'switch ')):
                out.append(p)
            p = l.find(e, p + len(e))
        return out
    for _ in range(rounds):
        lines = body.split('\n')
        scal = _scalar_names(head + body, len(head))
        cnt, firstl = {}, {}
        for li, l in enumerate(lines):
            if '(' not in l:
                continue
            for e in set(_paren_exprs(l)):
                if len(e) < minlen or re.search(r'\*\(|->|\[|[A-Za-z_]\w*\(|\bstk\b|&\s*[A-Za-z]|"| = |,|\(\*\)', e):
                    continue
                if re.search(r'\b(?:struct|volatile)\b', e) or not re.search(r'[-+*|&]|<<|>>', e):
                    continue
                if not _idents(e) <= scal:
                    continue
                k = len(occurrences(l, e))
                if k:
                    cnt[e] = cnt.get(e, 0) + k
                    firstl.setdefault(e, li)
        best = None
        for e, k in cnt.items():
            if k < minuses:
                continue
            vs = _idents(e)
            li = firstl[e]
            ind = re.match(r'^\s*', lines[li]).group()
            if lines[li].lstrip().startswith('} else'):      # cannot put a statement before `} else if`: go up to the head of the chain
                while li > 0 and not re.match(r'^%sif \(' % ind, lines[li]):
                    li -= 1
            if lines[li].lstrip().startswith('}') or re.match(r'^\s*\w+:', lines[li]):
                continue
            later = '\n'.join(lines[li:])
            if any(re.search(r'\b%s\s*(?:[-+*/|&^]|<<|>>)?= |\+\+%s|--%s|%s\+\+|%s--' % ((v,) * 5), later) for v in vs) or _addr_taken(head + body, vs):
                continue
            last = max(j for j in range(li, len(lines)) if occurrences(lines[j], e))
            depth, ok = 0, True                     # the statement at li must dominate every use
            for j in range(li, last + 1):
                if j > li and re.match(r'^\s*[A-Za-z_]\w*:', lines[j]):
                    ok = False
                    break
                for ch in lines[j]:
                    depth += ch == '{'
                    depth -= ch == '}'
                    if depth < 0:
                        ok = False
                if depth < 0 or not ok:
                    ok = False
                    break
            if not ok:
                continue
            score = (k - 1) * len(e)
            if best is None or score > best[0]:
                best = (score, e, li)
        if not best:
            break
        _, e, li = best
        name = 'qe%d' % n
        n += 1
        cmp_ = re.search(r'(?<![<>])[<>]=?(?![<>])|==|!=|!', e)
        isf = (bool(re.search(r'\bu\d+\b|\bf\d+\b|\d\.\d+f|\(float\)', e)) and not re.search(r'<<|>>|\||&', e)
               and not cmp_) or any(re.search(r'(?m)^\s*(?:register )?float %s;$' % re.escape(v), body) for v in _idents(e)) and not cmp_
        ind = re.match(r'^\s*', lines[li]).group()
        new = lines[:li] + ['%s%s = %s;' % (ind, name, e)]
        for l in lines[li:]:
            ps = occurrences(l, e)
            for p in reversed(ps):
                rep = '(%s)' % name if l[:p].endswith(('if ', 'while ', 'switch ')) else name
                l = l[:p] + rep + l[p + len(e):]
            new.append(l)
        body = '    register %s %s;\n' % ('float' if isf else 'int', name) + '\n'.join(new)
    return head + body


def _paren_exprs(s):
    """every balanced parenthesised substring of s"""
    st, out = [], []
    for i, ch in enumerate(s):
        if ch == '(':
            st.append(i)
        elif ch == ')' and st:
            j = st.pop()
            out.append(s[j:i + 1])
    return out



def compose_passes(fns):
    """One rewrite made of several, applied in order to the same text: shrink.py --stack measures and proves the result once.
    A pass that only pays after another (a member form after the register declarations go) is lost when each must pay alone."""
    def run(text):
        for fn in fns:
            text = fn(text)
        return text
    return run

LAST_PASSES = [
    ('selfcopy', 'GEN_SELFCOPY', drop_self_copies),         # frame slots stored back unchanged
    ('smod', 'GEN_SMOD', fold_signed_mask),                 # the sign sequence of a signed remainder by 2^k as one `%` line
    ('imask', 'GEN_IMASK', fold_imask),                     # set_imask's own mask and shifts not written again in its argument
    ('struct', 'GEN_STRUCT', struct_access),                # far field accesses as members (head_protos declares the structures)
    ('globase', 'GEN_GLOBASE', global_base),                # nearby fixed addresses off one base
    ('switch', 'GEN_SWITCH', chains_to_switch),             # a state chain of ifs as a switch
    ('copies', 'GEN_COPIES', merge_copies),                 # a result threaded through nesting levels by copies
    ('earlyret', 'GEN_EARLYRET', early_returns),            # the result returned at the end of each arm, not carried to one return
    ('deadframe', 'GEN_DEADFRAME', drop_dead_frame),        # a stack array nothing reads goes (after the self-copies are gone)
    ('hoist', 'GEN_HOIST', hoist_builtins),                 # a pure builtin called more than once with the same variable: once
    ('unused', 'GEN_UNUSED', drop_unused_locals),           # a local declared and never named: not declared (in a large function it still takes a register)
    ('pushstores', 'GEN_PUSHSTORES', drop_pushed_stores),   # the words pushed for a call are the call's arguments: not also stored in the frame
    ('regorder', 'GEN_REGORDER', order_registers),          # the `register` temporaries declared most-named first: SHC hands out its saved registers in that order
    ('rebase', 'GEN_REBASE', frame_rebase),                 # the stack array based at its first used word
]


def last_passes(text):
    """text through every LAST_PASSES rewrite whose GEN_<NAME> switch is not 0."""
    import os
    for _name, env, fn in LAST_PASSES:
        if os.environ.get(env, '1') != '0':
            text = fn(text)
    return text
