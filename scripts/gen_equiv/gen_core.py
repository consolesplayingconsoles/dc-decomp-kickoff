import re,struct,subprocess
BIN=open('1ST_READ.BIN','rb').read(); BASE=0x0C010000
def rd32(a): return struct.unpack_from('<I',BIN,a-BASE)[0]
M=0xffffffff
class Skip(Exception): pass
FUNCS={}
for _l in open('functions.txt'):
    _p=_l.split()
    if len(_p)>=4 and _p[0]=='F': FUNCS[int(_p[1],16)]=_p[3]

def fbits(f): return struct.unpack('<I',struct.pack('<f',f))[0]
def ffmt(bits):
    f=struct.unpack('<f',struct.pack('<I',bits))[0]
    if f!=f or abs(f)==float('inf'): return '(*(float*)&(unsigned int){0x%X})'%bits
    s='%.9g'%f
    if '.' not in s and 'e' not in s and 'n' not in s: s+='.0'
    return s+'f'
class Ctx:
    def __init__(s,name):
        s.name=name; s.R={}; s.FR={}; s.stmts=[]; s.ntemp=0; s.iuse=set(); s.fuse=set(); s.addrs=[]; s.fpul=None
        s.mem_addrs=[]; s.dirty=set()
    def gi(s,r):
        if r in s.dirty: raise Skip('dirty '+r)
        if r not in s.R:
            n=int(r[1:])
            if 4<=n<=7: s.R[r]=('s','a%d'%n); s.iuse.add(n)
            else: raise Skip('read '+r)
        return s.R[r]
    def gf(s,r):
        if r in s.dirty: raise Skip('dirty '+r)
        if r not in s.FR:
            n=int(r[2:])
            if 4<=n<=11: s.FR[r]=('s','f%d'%n); s.fuse.add(n)
            else: raise Skip('read '+r)
        return s.FR[r]
def ex(v):
    # int-valued expression string
    if isinstance(v,int): return '0x%X'%v if v>=0 else str(v)
    if v[0]=='s': return v[1]
    if v[0]=='e': return v[1]
    raise Skip('ex '+str(v))
def fx(v):
    if isinstance(v,int): return ffmt(v)
    return v[1]
def isint(v): return isinstance(v,int)
def iop(op,a,b=None):
    if isint(a) and (b is None or isint(b)):
        if op=='add': return (a+b)&M
        if op=='sub': return (a-b)&M
        if op=='and': return a&b
        if op=='or': return a|b
        if op=='xor': return a^b
        if op=='not': return (~a)&M
        if op=='neg': return (-a)&M
    if op=='add': return ('e','(%s + %s)'%(ex(a),ex(b)))
    if op=='sub': return ('e','(%s - %s)'%(ex(a),ex(b)))
    if op=='and': return ('e','(%s & %s)'%(ex(a),ex(b)))
    if op=='or': return ('e','(%s | %s)'%(ex(a),ex(b)))
    if op=='xor': return ('e','(%s ^ %s)'%(ex(a),ex(b)))
    if op=='not': return ('e','(~%s)'%ex(a))
    if op=='neg': return ('e','(-%s)'%ex(a))
    raise Skip(op)
def run(name,passthru=False):
    out=subprocess.run(['python3','tools/shdis.py','--func',name],capture_output=True,text=True).stdout.splitlines()[2:]
    ins=[]
    for l in out:
        m=re.match(r'([0-9a-f]{8}) ([0-9a-f]{4})\s+(\S+)\s*(.*)',l)
        if m: ins.append((m.group(3),m.group(4),int(m.group(1),16)))
    c=Ctx(name); c.in_prologue=True; c.T=None; c.blocks=[c.stmts]; c.stack={}; c.protos={}; c.ncalls=0; c.tail=None; c.pt=passthru; c.start_pc=ins[0][2] if ins else 0
    TY={'l':('int',4),'w':('short',2),'b':('signed char',1)}
    def addr_expr(base,off):
        # base: value; off: int or value
        b=base
        if isint(b) and isint(off): return ('const',(b+off)&M)
        if isinstance(b,tuple) and b[0]=='addr': raise Skip('addr')
        return ('expr','(%s + %s)'%(ex(b),ex(off)))
    def load(sz,ad):
        t='t%d'%c.ntemp; c.ntemp+=1
        ty=TY[sz][0]
        if ad[0]=='const': c.blocks[-1].append('%s %s = *(%s *)0x%X;'%('int',t,ty,ad[1])); c.mem_addrs.append(('c',ad[1]))
        else: c.blocks[-1].append('int %s = *(%s *)(%s);'%(t,ty,ad[1])); c.mem_addrs.append(('e',ad[1]))
        return ('e',t)
    def store(sz,ad,val):
        T={'l':'unsigned int','w':'unsigned short','b':'unsigned char'}[sz]
        v=ex(val)
        if ad[0]=='const': c.blocks[-1].append('*(%s *)0x%X = %s;'%(T,ad[1],v)); c.mem_addrs.append(('c',ad[1]))
        else: c.blocks[-1].append('*(%s *)(%s) = %s;'%(T,ad[1],v)); c.mem_addrs.append(('e',ad[1]))
    def fload(ad):
        t='u%d'%c.ntemp; c.ntemp+=1
        if ad[0]=='const': c.blocks[-1].append('float %s = *(float *)0x%X;'%(t,ad[1])); c.mem_addrs.append(('c',ad[1]))
        else: c.blocks[-1].append('float %s = *(float *)(%s);'%(t,ad[1])); c.mem_addrs.append(('e',ad[1]))
        return ('e',t)
    def fstore(ad,val):
        if ad[0]=='const': c.blocks[-1].append('*(float *)0x%X = %s;'%(ad[1],fx(val))); c.mem_addrs.append(('c',ad[1]))
        else: c.blocks[-1].append('*(float *)(%s) = %s;'%(ad[1],fx(val))); c.mem_addrs.append(('e',ad[1]))
    def parse_mem(s):
        s=s.strip()
        m=re.match(r'@\(0x[0-9a-f]+,pc\)',s)
        if m: return ('pc',)
        m=re.match(r'@\((\d+),(r\d+)\)$',s)
        if m: return ('disp',int(m.group(1)),m.group(2))
        m=re.match(r'@\(r0,(r\d+)\)$',s)
        if m: return ('r0',m.group(1))
        m=re.match(r'@(r\d+)$',s)
        if m: return ('ind',m.group(1))
        m=re.match(r'@(r\d+)\+$',s)
        if m: return ('post',m.group(1))
        m=re.match(r'@-(r\d+)$',s)
        if m: return ('pre',m.group(1))
        raise Skip('mem '+s)
    def memaddr(mm):
        k=mm[0]
        if k=='disp': return addr_expr(c.gi(mm[2]),mm[1])
        if k=='r0': return addr_expr(c.gi(mm[1]),c.gi('r0'))
        if k=='ind': return addr_expr(c.gi(mm[1]),0)
        raise Skip('memaddr')
    def exec1(mn,rawops):
        ops=rawops; com=''
        if ';' in rawops: ops,com=rawops.split(';',1); ops=ops.strip(); com=com.strip()
        a=[x.strip() for x in re.split(r',(?![^(]*\))',ops)] if ops else []
        if mn=='nop': return
        if mn=='rts': return 'rts'
        base=mn.split('.')[0]
        # stack frame handling
        if mn=='sts.l' and a[0]=='pr' and a[1]=='@-r15': return
        if mn=='lds.l' and a[0]=='@r15+' and a[1]=='pr': return
        if mn in('mov.l',) and a[0].startswith('r') and a[1]=='@-r15':
            n=int(a[0][1:])
            if c.in_prologue or (n>=8 and a[0] not in c.R): return
            raise Skip('push arg')
        if mn=='fmov.s' and a[0].startswith('fr') and a[1]=='@-r15':
            n=int(a[0][2:])
            if c.in_prologue or (n>=12 and a[0] not in c.FR): return
            raise Skip('fpush')
        if mn=='mov.l' and a[0]=='@r15+' and a[1].startswith('r'): return
        if mn=='fmov.s' and a[0]=='@r15+' : return
        if mn=='add' and a[1]=='r15': return
        if mn=='mov' and a[0]=='r15': raise Skip('addr of local')
        m15=re.match(r'@\((\d+),r15\)$',a[1]) if len(a)>1 else None
        m15b=(a[1]=='@r15') if len(a)>1 else False
        if mn in('mov.l','mov.w','mov.b','fmov.s') and (m15 or m15b) and (a[0].startswith('r') or a[0].startswith('fr')):
            off=int(m15.group(1)) if m15 else 0
            c.stack[(off,'f' if a[0].startswith('fr') else 'i')]=c.gf(a[0]) if a[0].startswith('fr') else c.gi(a[0]); return
        m15=re.match(r'@\((\d+),r15\)$',a[0]) if len(a)>1 else None
        m15b=(a[0]=='@r15') if len(a)>1 else False
        if mn in('mov.l','mov.w','mov.b','fmov.s') and (m15 or m15b) and (a[1].startswith('r') or a[1].startswith('fr')):
            off=int(m15.group(1)) if m15 else 0
            key=(off,'f' if a[1].startswith('fr') else 'i')
            if key not in c.stack: raise Skip('stack read')
            if mn=='mov.l' or mn=='fmov.s':
                if a[1].startswith('fr'): c.FR[a[1]]=c.stack[key]
                else: c.R[a[1]]=c.stack[key]
                return
            raise Skip('stack narrow')
        # constant loads
        if mn in('mov.l','mov.w') and re.match(r'@\(0x[0-9a-f]+,pc\)',a[0]):
            if mn=='mov.w':
                m2=re.match(r'=(-?\d+)',com); c.R[a[1]]=int(m2.group(1))&M
            else:
                mm=re.match(r'=([0-9a-fA-F]+)',com); c.R[a[1]]=int(mm.group(1),16)
            return
        if mn=='mova':
            m2=re.match(r'@\((0x[0-9a-f]+),pc\)',a[0]); c.R['r0']=('addr',int(m2.group(1),16)); return
        if mn=='mov' and a[0].startswith('#'): c.R[a[1]]=int(a[0][1:])&M; return
        if mn=='mov' and a[0].startswith('r'): c.R[a[1]]=c.gi(a[0]); return
        if mn=='add' and a[0].startswith('#'):
            v=c.gi(a[1])
            if isinstance(v,tuple) and v[0]=='addr': raise Skip('addr')
            c.R[a[1]]=iop('add',v,int(a[0][1:])&M if int(a[0][1:])>=0 else int(a[0][1:])&M); return
        if mn in('add','sub','and','or','xor') and a[0].startswith('r'):
            x=c.gi(a[1]); y=c.gi(a[0])
            for v in (x,y):
                if isinstance(v,tuple) and v[0]=='addr': raise Skip('addr')
            c.R[a[1]]=iop(mn,x,y); return
        if mn in('and','or','xor') and a[0].startswith('#'):
            v=c.gi(a[1]); c.R[a[1]]=iop(mn,v,int(a[0][1:])&0xff); return
        if mn in ('not','neg'): c.R[a[1]]=iop(mn,c.gi(a[0])); return
        if mn in ('mul.l','muls.w','mulu.w'):
            x=c.gi(a[0]); y=c.gi(a[1])
            cast={'mul.l':'int','muls.w':'short','mulu.w':'unsigned short'}[mn]
            c.macl=('e','((%s)%s * (%s)%s)'%(cast,ex(y),cast,ex(x))) if mn!='mul.l' else ('e','(%s * %s)'%(ex(y),ex(x))); return
        if mn=='sts' and a[0]=='macl':
            if getattr(c,'macl',None) is None: raise Skip('macl')
            c.R[a[1]]=c.macl; return
        if mn=='shll': v=c.gi(a[0]); c.R[a[0]]=(v<<1)&M if isint(v) else ('e','(%s << 1)'%ex(v)); return
        if mn in('shll2','shll8','shll16'):
            n={'shll2':2,'shll8':8,'shll16':16}[mn]; v=c.gi(a[0]); c.R[a[0]]=(v<<n)&M if isint(v) else ('e','(%s << %d)'%(ex(v),n)); return
        if mn in('shlr','shlr2','shlr8','shlr16'):
            n={'shlr':1,'shlr2':2,'shlr8':8,'shlr16':16}[mn]; v=c.gi(a[0]); c.R[a[0]]=(v>>n) if isint(v) else ('e','((unsigned int)%s >> %d)'%(ex(v),n)); return
        if mn=='shar': v=c.gi(a[0]); c.R[a[0]]=('e','(%s >> 1)'%ex(v)) if not isint(v) else ((v>>1)|(v&0x80000000)); return
        if mn=='extu.b': v=c.gi(a[0]); c.R[a[1]]=(v&0xff) if isint(v) else ('e','(unsigned char)%s'%ex(v)); return
        if mn=='extu.w': v=c.gi(a[0]); c.R[a[1]]=(v&0xffff) if isint(v) else ('e','(unsigned short)%s'%ex(v)); return
        if mn=='exts.b': v=c.gi(a[0]); c.R[a[1]]=('e','(signed char)%s'%ex(v)) if not isint(v) else (((v&0xff)^0x80)-0x80)&M; return
        if mn=='exts.w': v=c.gi(a[0]); c.R[a[1]]=('e','(short)%s'%ex(v)) if not isint(v) else (((v&0xffff)^0x8000)-0x8000)&M; return
        if mn in('mov.l','mov.w','mov.b'):
            sz=mn[-1]
            if a[0].startswith('r'):   # store
                mm=parse_mem(a[1]); v=c.gi(a[0])
                if isinstance(v,tuple) and v[0]=='addr': raise Skip('addr val')
                if mm[0]=='pre':
                    nb=c.gi(mm[1]); step={'l':4,'w':2,'b':1}[sz]; nb=iop('sub',nb,step); c.R[mm[1]]=nb; store(sz,addr_expr(nb,0),v); return
                store(sz,memaddr(mm),v); return
            else:   # load
                mm=parse_mem(a[0])
                if mm[0]=='post':
                    b=c.gi(mm[1]); t=load(sz,addr_expr(b,0)); step={'l':4,'w':2,'b':1}[sz]; c.R[mm[1]]=iop('add',b,step); c.R[a[1]]=t; return
                c.R[a[1]]=load(sz,memaddr(mm)); return
        # floats
        if mn=='fldi0': c.FR[a[0]]=0; return
        if mn=='fldi1': c.FR[a[0]]=0x3f800000; return
        if mn=='fmov' and a[0].startswith('fr'): c.FR[a[1]]=c.gf(a[0]); return
        if mn=='fmov.s':
            if a[0].startswith('fr'):   # store
                mm=parse_mem(a[1]); v=c.gf(a[0])
                if mm[0]=='pre':
                    nb=iop('sub',c.gi(mm[1]),4); c.R[mm[1]]=nb; fstore(addr_expr(nb,0),v); return
                fstore(memaddr(mm),v); return
            else:
                mm=parse_mem(a[0])
                if mm[0]=='ind' and isinstance(c.gi(mm[1]),tuple) and c.gi(mm[1])[0]=='addr':
                    c.FR[a[1]]=rd32(c.gi(mm[1])[1]); return
                if mm[0]=='post':
                    b=c.gi(mm[1]); c.FR[a[1]]=fload(addr_expr(b,0)); c.R[mm[1]]=iop('add',b,4); return
                c.FR[a[1]]=fload(memaddr(mm)); return
        if mn in('fadd','fsub','fmul','fdiv'):
            x=c.gf(a[1]); y=c.gf(a[0]); op={'fadd':'+','fsub':'-','fmul':'*','fdiv':'/'}[mn]
            c.FR[a[1]]=('e','(%s %s %s)'%(fx(x),op,fx(y))); return
        if mn=='fneg': c.FR[a[0]]=('e','(-%s)'%fx(c.gf(a[0]))); return
        if mn=='lds' and a[1]=='fpul': c.fpul=c.gi(a[0]); return
        if mn=='float' and a[0]=='fpul': c.FR[a[1]]=('e','(float)%s'%ex(c.fpul)); return
        if mn=='ftrc': c.fpul=('e','(int)%s'%fx(c.gf(a[0]))); return
        if mn=='sts' and a[0]=='fpul': c.R[a[1]]=c.fpul; return
        raise Skip(mn+' '+rawops)
    addr2idx={x[2]:i for i,x in enumerate(ins)}
    def do_call(fname,tail=False):
        iargs=[]; 
        avail=[]
        for n in range(4,8):
            r='r%d'%n
            if r in c.R and r not in c.dirty: avail.append(n)
            elif r not in c.R and c.pt and c.ncalls==0 and r not in c.dirty: avail.append(n)
        fav=[]
        for n in range(4,12):
            r='fr%d'%n
            if r in c.FR and r not in c.dirty: fav.append(n)
        ia=[]
        k=4
        while k in avail: ia.append(k); k+=1
        if any(x>=k for x in avail): raise Skip('arg gap')
        fa=[]; k=4
        while k in fav: fa.append(k); k+=1
        if any(x>=k for x in fav): raise Skip('farg gap')
        args=[]; types=[]
        for n in ia:
            v=c.gi('r%d'%n)
            if isinstance(v,tuple) and v[0]=='addr': raise Skip('addr arg')
            args.append(ex(v)); types.append('int')
        for n in fa: args.append(fx(c.gf('fr%d'%n))); types.append('float')
        sig=tuple(types)
        if fname in c.protos and c.protos[fname]!=sig: raise Skip('proto conflict')
        c.protos[fname]=sig
        call='%s(%s)'%(fname,', '.join(args))
        if tail:
            c.tail=call; c.blocks[-1].append('@@TAIL@@'); return
        t='t%d'%c.ntemp; c.ntemp+=1
        c.blocks[-1].append('int %s = %s;'%(t,call))
        c.ncalls+=1
        for n in range(1,8):
            c.R.pop('r%d'%n,None)
        for n in range(0,12): c.FR.pop('fr%d'%n,None)
        c.R['r0']=('e',t); c.fpul=None

    def cond_expr(neg):
        t=c.T
        if t is None: raise Skip('no T')
        return t
    def set_T(mn,a):
        def v(x):
            if x.startswith('#'): return str(int(x[1:]))
            return ex(c.gi(x))
        def fv(x): return fx(c.gf(x))
        if mn=='tst':
            if a[0].startswith('#'): c.T='((%s & %d) == 0)'%(ex(c.gi('r0')),int(a[0][1:])&0xff)
            elif a[0]==a[1]: c.T='(%s == 0)'%ex(c.gi(a[0]))
            else: c.T='((%s & %s) == 0)'%(ex(c.gi(a[1])),ex(c.gi(a[0])))
            return
        if mn.startswith('cmp/'):
            op=mn[4:]
            if op=='eq': c.T='(%s == %s)'%(ex(c.gi(a[1])),v(a[0])) if not a[0].startswith('#') else '(%s == %d)'%(ex(c.gi(a[1])),int(a[0][1:]))
            elif op=='pl': c.T='((int)%s > 0)'%ex(c.gi(a[0]))
            elif op=='pz': c.T='((int)%s >= 0)'%ex(c.gi(a[0]))
            else:
                x=ex(c.gi(a[1])); y=ex(c.gi(a[0]))
                if op=='ge': c.T='((int)%s >= (int)%s)'%(x,y)
                elif op=='gt': c.T='((int)%s > (int)%s)'%(x,y)
                elif op=='hi': c.T='((unsigned int)%s > (unsigned int)%s)'%(x,y)
                elif op=='hs': c.T='((unsigned int)%s >= (unsigned int)%s)'%(x,y)
                else: raise Skip(mn)
            return
        if mn=='fcmp/gt': c.T='(%s > %s)'%(fx(c.gf(a[1])),fx(c.gf(a[0]))); return
        if mn=='fcmp/eq': c.T='(%s == %s)'%(fx(c.gf(a[1])),fx(c.gf(a[0]))); return
        raise Skip(mn)
    def parse_ops(raw):
        ops=raw
        if ';' in raw: ops=raw.split(';',1)[0].strip()
        return [x.strip() for x in re.split(r',(?![^(]*\))',ops)] if ops else []
    def target_of(raw):
        m=re.search(r'0x([0-9a-f]{8})',raw); 
        if not m: raise Skip('target'); 
        return int(m.group(1),16)
    def regs_state(): return (dict(c.R),dict(c.FR),c.fpul)
    def run_range(i,end):
        # executes ins[i:end]; returns index reached ('rts' returns -1)
        while i<end:
            mn,ops,pc=ins[i]
            if c.in_prologue and not (mn=='sts.l' or (mn in('mov.l','fmov.s') and parse_ops(ops)[1:]==['@-r15']) or (mn=='add' and parse_ops(ops)[1:]==['r15'])):
                c.in_prologue=False
            if mn in ('jsr','bsr'):
                tgt=None
                if mn=='bsr': tgt=target_of(ops)
                else:
                    rg=parse_ops(ops)[0].strip('@')
                    v=c.gi(rg)
                    if not isinstance(v,int): raise Skip('indirect call')
                    tgt=v
                if tgt not in FUNCS: raise Skip('callee unknown %x'%tgt)
                # delay slot executes before the call
                exec1(ins[i+1][0],ins[i+1][1])
                do_call(FUNCS[tgt]); i+=2; continue
            if mn=='bra' or mn=='jmp':
                # tail call?
                if mn=='bra':
                    tgt=target_of(ops)
                    if tgt in addr2idx: raise Skip('bra inner')
                else:
                    rg=parse_ops(ops)[0].strip('@'); v=c.gi(rg)
                    if not isinstance(v,int): raise Skip('indirect jmp')
                    tgt=v
                    if tgt in addr2idx: raise Skip('jmp inner')
                if tgt not in FUNCS: raise Skip('tail unknown')
                exec1(ins[i+1][0],ins[i+1][1])
                do_call(FUNCS[tgt],tail=True)
                return -1
            if mn=='rts':
                if i+1<len(ins): exec1(ins[i+1][0],ins[i+1][1])
                if len(c.blocks)>1:
                    v=c.R.get('r0')
                    e='None' if v is None or 'r0' in c.dirty or (isinstance(v,tuple) and v[0]=='addr') else ex(v)
                    c.blocks[-1].append('@@RET:%s@@'%e)
                    return -2
                return -1
            if mn.startswith('cmp') or mn.startswith('tst') or mn.startswith('fcmp'):
                set_T(mn,parse_ops(ops)); i+=1; continue
            if mn in ('bt','bf','bt/s','bf/s'):
                tgt=target_of(ops)
                if tgt<=pc or tgt not in addr2idx: raise Skip('backward')
                j=addr2idx[tgt]
                delay=mn.endswith('/s')
                if delay: exec1(ins[i+1][0],ins[i+1][1])
                body_start=i+(2 if delay else 1)
                cond=cond_expr(False)
                if cond is None: raise Skip('T')
                run_cond=('!%s'%cond) if mn.startswith('bt') else cond
                # if-else?
                last=j-1
                # find last real instruction before target (skip nop)
                lastbra=None
                # bra at j-2 (delay at j-1) pattern
                if j-2>=body_start and ins[j-2][0]=='bra':
                    lastbra=j-2
                pre=regs_state(); T0=c.T
                if lastbra is not None:
                    end_tgt=target_of(ins[lastbra][1])
                    if end_tgt<=ins[lastbra][2] or end_tgt not in addr2idx: raise Skip('bra back')
                    k=addr2idx[end_tgt]
                    blk1=[]; c.blocks.append(blk1)
                    r=run_range(body_start,lastbra)
                    if r==-1: raise Skip('rts in block')
                    ret1=(r==-2)
                    if not ret1: exec1(ins[lastbra+1][0],ins[lastbra+1][1])
                    st1=regs_state(); c.blocks.pop()
                    c.R,c.FR,c.fpul=dict(pre[0]),dict(pre[1]),pre[2]; c.T=T0
                    blk2=[]; c.blocks.append(blk2)
                    r=run_range(j,k)
                    if r==-1: raise Skip('rts in else')
                    ret2=(r==-2)
                    st2=regs_state(); c.blocks.pop()
                    if ret1 and ret2: raise Skip('both return')
                    if ret1: st1=st2
                    if ret2: st2=st1
                    for regs,idx in ((0,0),):
                        pass
                    def merge(p,a,b):
                        for r in set(a)|set(b)|set(p):
                            if a.get(r)!=p.get(r) or b.get(r)!=p.get(r):
                                if not (a.get(r)==b.get(r)): c.dirty.add(r)
                                else: pass
                    c.R=dict(st1[0]); c.FR=dict(st1[1]); c.fpul=st1[2]
                    def phi(regmap1,regmap2,target,isf):
                        for r in sorted(set(regmap1)|set(regmap2)):
                            v1=regmap1.get(r); v2=regmap2.get(r)
                            if v1==v2: continue
                            if v1 is None or v2 is None or (isinstance(v1,tuple) and v1[0]=='addr') or (isinstance(v2,tuple) and v2[0]=='addr'):
                                c.dirty.add(r); target.pop(r,None); continue
                            var=('u%d' if isf else 't%d')%c.ntemp; c.ntemp+=1
                            ty='float' if isf else 'int'
                            c.blocks[-1].append('%s %s;'%(ty,var))
                            f=fx if isf else ex
                            blk1.append('%s = %s;'%(var,f(v1))); blk2.append('%s = %s;'%(var,f(v2)))
                            target[r]=('e',var)
                    phi(st1[0],st2[0],c.R,False); phi(st1[1],st2[1],c.FR,True)
                    c.blocks[-1].append('if (%s) {\n%s\n    } else {\n%s\n    }'%(run_cond,'\n'.join('    '+x for x in blk1),'\n'.join('    '+x for x in blk2)))
                    i=k; c.T=None; continue
                blk=[]; c.blocks.append(blk)
                r=run_range(body_start,j)
                st=regs_state(); c.blocks.pop()
                if r==-1: raise Skip('rts in block')
                if r==-2: st=pre
                c.R,c.FR,c.fpul=dict(pre[0]),dict(pre[1]),pre[2]
                def phi1(post,preM,target,isf):
                    for r_ in sorted(set(post)|set(preM)):
                        v1=post.get(r_); v0=preM.get(r_)
                        if v1==v0: continue
                        if v1 is None or v0 is None or (isinstance(v1,tuple) and v1[0]=='addr') or (isinstance(v0,tuple) and v0[0]=='addr'):
                            c.dirty.add(r_); target.pop(r_,None); continue
                        var=('u%d' if isf else 't%d')%c.ntemp; c.ntemp+=1
                        ty='float' if isf else 'int'
                        f=fx if isf else ex
                        c.blocks[-1].append('%s %s = %s;'%(ty,var,f(v0)))
                        blk.append('%s = %s;'%(var,f(v1)))
                        target[r_]=('e',var)
                phi1(st[0],pre[0],c.R,False); phi1(st[1],pre[1],c.FR,True)
                if blk: c.blocks[-1].append('if (%s) {\n%s\n    }'%(run_cond,'\n'.join('    '+x for x in blk)))
                i=j; c.T=None; continue
            if mn in ('braf','bsrf','rte','trapa','dt'): raise Skip('flow '+mn)
            exec1(mn,ops); i+=1
        return i
    r=run_range(0,len(ins))
    return c
