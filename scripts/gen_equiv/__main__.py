"""Writes Equivalent C for the functions that need no thinking, and checks each against the original.

    python3 tools/gen_equiv <max function size, default 200>      (run in the repo, like equiv.py)

For every function classify.py calls convertible and no C covers yet, it symbolically executes the SH-4 code: constants,
loads and stores, integer and single-precision float arithmetic, forward if / else blocks, and calls to named functions
(arguments are the registers r4-r7 / fr4-fr11 set before the call). Anything else (loops, a jump into the middle of a
function, stack arguments, multiply, address of a local) is skipped. The C goes to src/gen_<letter>.c, the cases to
tests/gen_<letter>/ (22 cases: values from a fixed set plus the constants the code compares against, calls answered with
varied results), and a function stays only if tools/equiv.py calls it Equivalent: first as a void function, then returning
r0 / fr0, then passing the caller's registers through to the first call.

The result is generated code, plain (temps t0, t1, hex stores, int prototypes) and checked on random values: a branch the
cases never reach can pass by luck. Report it apart from hand-written C. Needs: functions.txt, tools/shdis.py,
tools/classify.py, tools/equiv.py, 1ST_READ.BIN."""
import sys,json,os,shutil,glob,re,subprocess,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import gen_pipe,gen_drv,gen_core
maxsize=int(sys.argv[1]) if len(sys.argv)>1 else 200
eq=set(open('tests/equivalent.txt').read().split())
defined=set()
for f in glob.glob('src/*.c'):
    t=open(f,errors='replace').read()
    defined|=set(re.findall(r'^[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;{]*\)\s*\{',t,flags=re.M))
ver=set()
for l in open('sdk-verified.txt'):
    if not l.startswith('#'): ver.update(l.split())
cand=[]; cnt=collections.Counter()
for l in subprocess.run(['python3','tools/classify.py'],capture_output=True,text=True).stdout.splitlines():
    p=l.split()
    if len(p)>=4 and p[-1]=='ok' and p[2] not in eq and p[2] not in ver and not p[2].startswith('_') and int(p[1])<=maxsize and p[2] not in defined:
        try: gen_core.run(p[2]); cand.append(p[2])
        except gen_core.Skip as e: cnt[re.sub(r'[0-9a-f]{4,}','',str(e).split()[0] if str(e) else '?')]+=1
        except Exception as e: cnt['EXC '+type(e).__name__]+=1
print(len(cand),cnt.most_common(10),flush=True)
existing=[os.path.basename(f)[4:-2] for f in glob.glob('src/gen_?.c')]
letters=[x for x in 'abcdefghijklmnopqrstuvwxyz' if x not in existing]
remaining=list(cand); final=[]
rounds=[(0,False),(1,False),(0,True),(1,True),(2,False)]
done=set()
for ri,(vi,pt) in enumerate(rounds):
    if not remaining: break
    items=[]
    for n in remaining:
        try:
            vs=gen_pipe.variants(n,pt)
            if vi>=len(vs): continue
            s,c=gen_drv.build(n,vs[vi],pt)
            if n in c.protos: continue
            t=gen_drv.tests(n,c,s)
            items.append((n,s,t,c.protos))
        except Exception as e: pass
    if not items: continue
    stem='gen_x%d'%ri
    passed,failed,deferred,dropped,err=gen_pipe.run_file_robust(stem,items)
    print(ri,vi,pt,'items',len(items),'passed',len(passed),'failed',len(failed),'dropped',len(dropped),err[:100],flush=True)
    keep=[it for it in items if it[0] in passed]
    done|=set(passed)
    final.append((stem,keep,vi,pt))
    remaining=[n for n in remaining if n not in passed]
    for f in glob.glob('src/gen_x*.c'): os.remove(f)
    for d in glob.glob('tests/gen_x*'): shutil.rmtree(d)
k=0
for stem,keep,vi,pt in final:
    if not keep: continue
    protos={}
    for it in keep:
        for a,b in it[3].items(): protos[a]=b
    fn='gen_%s'%letters[k]; k+=1
    head='/* Straight-line functions with calls and guards (batch %s): generated from the code and checked by tests. Calls are\n   to the game or library function at the address, with the arguments in r4-r7 and fr4-fr11 as set. */\n\n'%fn+gen_drv.protos_text(protos)+'\n\n'
    open('src/%s.c'%fn,'w').write(head+'\n'.join(i[1] for i in keep))
    shutil.rmtree('tests/%s'%fn,ignore_errors=True); os.makedirs('tests/%s'%fn)
    for it in keep: json.dump(it[2],open('tests/%s/%s.json'%(fn,it[0]),'w'),indent=1)
    r=subprocess.run(['python3','tools/equiv.py','-q','src/%s.c'%fn],capture_output=True,text=True)
    print(fn,len(keep),(r.stdout+r.stderr).strip().splitlines()[-1],flush=True)
print('total',len(done),'remaining',len(remaining))
