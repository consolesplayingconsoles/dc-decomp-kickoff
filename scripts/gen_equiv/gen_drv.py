import sys,re,json,os,subprocess,struct,random
sys.path.insert(0,os.path.dirname(__file__))
import gen_core as G
Skip=G.Skip
def build(name,ret,passthru=False):
    c=G.run(name,passthru)
    if not c.stmts: raise Skip('empty')
    ip=sorted(c.iuse); fp=sorted(c.fuse)
    params=[]
    if ip:
        for n in range(4,max(ip)+1): params.append('int a%d'%n)
    if fp:
        for n in range(4,max(fp)+1): params.append('float f%d'%n)
    text='\n'.join(c.stmts)
    decls=[]
    def hoist(m):
        decls.append('%s %s;'%(m.group(1),m.group(2))); return '%s = '%m.group(2)
    text=re.sub(r'\b(int|float) ([tu]\d+) = ',hoist,text)
    def hoist2(m):
        decls.append('%s %s;'%(m.group(1),m.group(2))); return ''
    text=re.sub(r'^\s*(int|float) ([tu]\d+);$',hoist2,text,flags=re.M)
    text=re.sub(r'\n[ \t]*(?=\n)','',text)
    frame_decl=None
    if c.frame:
        W=(c.maxD+3)//4+1
        frame_decl='int stk[%d];'%W
        text=re.sub(r'@@F:(-?\d+)@@',lambda m:str(4*W+int(m.group(1))),text)
    rt='void'
    if '@@TAIL:' in text:
        if ret=='void': text=re.sub(r'@@TAIL:(.*?)@@',lambda m:m.group(1)+';\nreturn;',text)
        else: text=re.sub(r'@@TAIL:(.*?)@@',lambda m:'return %s;'%m.group(1),text); rt='int'
    if not c.terminated:
        if ret=='r0':
            v=c.R.get('r0')
            if v is None or v==G.DIRTY or (isinstance(v,tuple) and v[0]=='addr'): raise Skip('no r0')
            rt='int'; text+='\nreturn %s;'%G.ex(v)
        elif ret=='fr0':
            v=c.FR.get('fr0')
            if v is None or v==G.DIRTY: raise Skip('no fr0')
            rt='float'; text+='\nreturn %s;'%G.fx(v)
    elif ret=='r0': rt='int'
    elif ret=='fr0': rt='float'
    def retfix(m):
        e,f=m.group(1),m.group(2)
        if ret=='void': return 'return;'
        if ret=='fr0':
            if f=='None': raise Skip('no fr0')
            return 'return %s;'%f
        return 'return 0;' if e=='None' else 'return %s;'%e
    text=re.sub(r'@@RET:(.*?)@\|@(.*?)@@',retfix,text)
    if ret=='void': text=re.sub(r'\n?return;\Z','',text)
    # prune dead assignments of pure values (phi leftovers)
    def prune(text,decls):
        changed=True
        while changed:
            changed=False
            for dcl in list(decls):
                nm=dcl.split()[1].rstrip(';')
                occ=len(re.findall(r'\b%s\b'%nm,text))
                lhs=re.findall(r'^\s*%s = ([^\n]*);$'%nm,text,flags=re.M)
                if occ==len(lhs) and all(('*(' not in r and not re.search(r'[A-Za-z_]\w*\s*\(',r)) for r in lhs):
                    text=re.sub(r'^\s*%s = [^\n]*;\n?'%nm,'',text,flags=re.M); decls.remove(dcl); changed=True
            t2=re.sub(r'if \([^\n]*\) \{\s*\}','',text)
            t2=re.sub(r' else \{\s*\}','',t2)
            if t2!=text: text=t2; changed=True
        return text
    text=prune(text,decls)
    # unused call results: drop the temp
    for d in list(decls):
        nm=d.split()[1].rstrip(';')
        if len(re.findall(r'\b%s\b'%nm,text))==1 and re.search(r'\b%s = [A-Za-z_]\w*\('%nm,text):
            text=re.sub(r'\b%s = '%nm,'',text); decls.remove(d)
    body=text.strip('\n').split('\n')
    src='%s %s(%s)\n{\n%s\n}\n'%(rt,name,', '.join(params) if params else 'void','\n'.join(['    '+d for d in decls+([frame_decl] if frame_decl else [])]+(['']if decls or frame_decl else [])+['    '+s for s in body]))
    return src,c
def addr_vals(c,basemap):
    """The addresses the code touches that follow from the argument values alone (None for one that depends on a loaded
    value or a loop variable)."""
    res=[]
    for kind,e in c.mem_addrs:
        if kind=='c': res.append(e); continue
        if re.search(r'\b[tu]\d+\b|\bstk\b',e): res.append(None); continue
        ex=e
        for k,v in basemap.items(): ex=re.sub(r'\b%s\b'%k,str(v),ex)
        if not re.match(r'^[\(\)\s\w\+\-]*$',ex): raise Skip('addr expr '+e)
        try: res.append(eval(ex)&0xffffffff)
        except Exception: raise Skip('eval')
    return res
def stack_top():
    """Where the simulator's stack pointer starts: the first stack argument of a function is there."""
    try:
        sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
        import sh4sim
        return sh4sim.STACK_TOP-0x100
    except Exception: raise Skip('no simulator for stack arguments')
def original_runs(name,case):
    """How many instructions the original takes on a case (None when it does not finish): lets the generator keep only the
    cases a loop actually ends on. Needs tools/sh4sim.py next to this directory; without it every case is kept."""
    try:
        sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..'))
        import sh4sim
    except Exception: return 0
    start,size=G.SPANS[name]
    base=int(open('BASE').read().strip(),16)
    r=sh4sim.run(dict(case,exe='1ST_READ.BIN',base='%08X'%base,entry='%08X'%start,end='%08X'%(start+size),steps=100000),'.',deep=lambda t:False)
    return None if r['error'] else r['steps']
def tests(name,c,src):
    ip=sorted(c.iuse); fp=sorted(c.fuse)
    loopy=c.has_loop
    addr_params=set()
    for kind,e in c.mem_addrs:
        if kind=='e':
            for m in re.findall(r'\ba(\d)\b',e): addr_params.add(int(m))
    basemap={}
    for n in ip:
        if n in addr_params: basemap['a%d'%n]=0x0C800000+(n-4)*0x10000
    consts=set()
    for m in re.findall(r'(?:==|&|>=|>|<=|<|\+|-)\s*\(?(0x[0-9A-Fa-f]+|\d+)',src):
        try:
            v=int(m,0); consts|={v&0xffffffff,(v+1)&0xffffffff,(v-1)&0xffffffff,(v<<1)&0xffffffff}
        except Exception: pass
    base=[0,1,2,3,4,5,8,16,0x100,0xFFFFFFFF,0x7FFFFFFF,0x80000000,0xFFFFFFFE,0x40000000]
    floats=(0.0,1.0,2.5,-3.0,100.0,1e9)
    if loopy:
        # a loop runs as often as its bound says: keep the values small so that the original ends
        base=[0,1,2,3,4,5,8,16,0x40,0xFFFFFFFF,0xFFFFFFFE]
        consts={x for x in consts if x<=0x100 or x>=0xFFFFFF00}
        floats=(0.0,1.0,2.5,-3.0,0.1)
    for f in floats: base.append(struct.unpack('<I',struct.pack('<f',f))[0])
    V=sorted(set(base)|consts)
    small=[v for v in V if v<=0x100 or v>=0xFFFFFF00]
    ncalls=len(re.findall(r'\b(?:t\d+ = |return )?[A-Za-z_]\w*\([^()]*\);',src))+4
    if loopy: ncalls=max(ncalls,48)
    cases=[]
    rng=random.Random(hash(name)&0xffff)
    chained=any(k=='e' and re.search(r'\b[tu]\d+\b|\bstk\b',e) for k,e in c.mem_addrs)
    for i in range(60 if (loopy or chained) else 22):
        bm=dict(basemap)
        for n in ip:
            if n not in addr_params: bm['a%d'%n]=rng.choice(V)
        addrs=addr_vals(c,bm)
        poke={}
        forced=V[i] if i<12 and i<len(V) else None
        pool=(small if loopy else V)+([0x0C900000,0x0C910000,0x0C920040] if chained else [])      # some loaded words are pointers
        if loopy or chained:
            # addresses that follow loop variables or loaded values cannot be worked out: fill the memory the pointers point at
            for n in sorted(addr_params):
                b=bm['a%d'%n]&~3
                words=[forced if forced is not None and rng.random()<0.85 else rng.choice(pool) for _ in range(64)]
                poke['%08X'%((b-0x20)&0xffffffff)]=struct.pack('<16I',*[rng.choice(pool) for _ in range(16)]).hex()
                poke['%08X'%b]=struct.pack('<64I',*words).hex()
        for a in addrs:
            if a is None: continue
            w=forced if forced is not None else rng.choice(pool)
            poke['%08X'%((a&~3)&0xffffffff)]=struct.pack('<II',w,rng.choice(pool)).hex()
        regs={}
        for n in ip:
            if n<8: regs['r%d'%n]='%08X'%(bm['a%d'%n]&0xffffffff)
            else: poke['%08X'%(stack_top()+4*(n-8))]=struct.pack('<I',bm['a%d'%n]&0xffffffff).hex()
        for n in fp: regs['fr%d'%n]=rng.choice(floats)
        d={'about':'case %d'%i,'poke':poke}
        if regs: d['regs']=regs
        if c.ncalls or c.tail:
            d['calls']=[dict({'r0':'%08X'%rng.choice(pool)},**({'poke_arg':{r:struct.pack('<8I',*[rng.choice(pool) for _ in range(8)]).hex() for r in sorted(c.frame_regs)}} if c.frame_regs else {})) for _ in range(ncalls)]
        cases.append(d)
    if loopy or chained:
        kept=[d for d in cases if original_runs(name,d) is not None]
        if len(kept)<12: raise Skip('the original does not finish on the cases')
        cases=kept[:22]
    return {'dev':cases[:15],'holdout':cases[15:]}
def protos_text(protos):
    out=[]
    for n,sig in sorted(protos.items()):
        out.append('int %s(%s);'%(n,', '.join(sig) if sig else 'void'))
    return '\n'.join(out)
