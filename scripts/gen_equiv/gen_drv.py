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
    rt='void'
    tail=c.tail
    if '@@TAIL@@' in text:
        if ret=='void': text=text.replace('@@TAIL@@',tail+';')
        else: text=text.replace('@@TAIL@@','return %s;'%tail); rt='int'
    elif ret=='r0':
        v=c.R.get('r0')
        if v is None or 'r0' in c.dirty or (isinstance(v,tuple) and v[0]=='addr'): raise Skip('no r0')
        rt='int'; text+='\nreturn %s;'%G.ex(v)
    elif ret=='fr0':
        v=c.FR.get('fr0')
        if v is None or 'fr0' in c.dirty: raise Skip('no fr0')
        rt='float'; text+='\nreturn %s;'%G.fx(v)
    # prune dead assignments of pure values (phi leftovers)
    def prune(text,decls):
        changed=True
        while changed:
            changed=False
            for dcl in list(decls):
                nm=dcl.split()[1].rstrip(';')
                occ=len(re.findall(r'\b%s\b'%nm,text))
                lhs=re.findall(r'^\s*%s = ([^\n]*);$'%nm,text,flags=re.M)
                if occ==len(lhs) and all(('*(' not in r and '(' not in re.sub(r'\((int|unsigned int|float|unsigned char|unsigned short|short|signed char)\)|\(\(|\)\)|[()]','',r) ) for r in lhs):
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
    body=text.split('\n')
    src='%s %s(%s)\n{\n%s\n}\n'%(rt,name,', '.join(params) if params else 'void','\n'.join(['    '+d for d in decls]+(['']if decls else [])+['    '+s for s in body]))
    return src,c
def addr_vals(c,basemap):
    res=[]
    for kind,e in c.mem_addrs:
        if kind=='c': res.append(e); continue
        if re.search(r'\b[tu]\d+\b',e): raise Skip('chained')
        ex=e
        for k,v in basemap.items(): ex=re.sub(r'\b%s\b'%k,str(v),ex)
        if not re.match(r'^[\(\)\s\w\+\-]*$',ex): raise Skip('addr expr '+e)
        try: res.append(eval(ex)&0xffffffff)
        except Exception: raise Skip('eval')
    return res
def tests(name,c,src):
    ip=sorted(c.iuse); fp=sorted(c.fuse)
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
    for f in (0.0,1.0,2.5,-3.0,100.0,1e9): base.append(struct.unpack('<I',struct.pack('<f',f))[0])
    V=sorted(set(base)|consts)
    ncalls=len(re.findall(r'= [A-Za-z_]\w*\(',src))+src.count('return F')+0
    ncalls=len(re.findall(r'\b(?:t\d+ = |return )?[A-Za-z_]\w*\([^()]*\);',src))+4
    cases=[]
    rng=random.Random(hash(name)&0xffff)
    for i in range(22):
        bm=dict(basemap)
        for n in ip:
            if n not in addr_params: bm['a%d'%n]=rng.choice(V)
        addrs=addr_vals(c,bm)
        poke={}
        forced=V[i] if i<12 and i<len(V) else None
        for a in addrs:
            w=forced if forced is not None else rng.choice(V)
            poke['%08X'%((a&~3)&0xffffffff)]=struct.pack('<II',w,rng.choice(V)).hex()
        regs={}
        for n in ip: regs['r%d'%n]='%08X'%(bm['a%d'%n]&0xffffffff)
        for n in fp: regs['fr%d'%n]=rng.choice((2.5,-3.0,0.0,100.0,1e9,0.1))
        d={'about':'case %d'%i,'poke':poke}
        if regs: d['regs']=regs
        if c.ncalls or c.tail:
            d['calls']=[{'r0':'%08X'%rng.choice(V)} for _ in range(ncalls)]
        cases.append(d)
    return {'dev':cases[:15],'holdout':cases[15:]}
def protos_text(protos):
    out=[]
    for n,sig in sorted(protos.items()):
        out.append('int %s(%s);'%(n,', '.join(sig) if sig else 'void'))
    return '\n'.join(out)
