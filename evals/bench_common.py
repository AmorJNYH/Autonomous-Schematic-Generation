"""Shared cache-only helpers for ASG calibration. No third-party input in Git."""
from pathlib import Path
import json,hashlib,os,subprocess,sys,time,uuid,shutil,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
PY=sys.executable
sys.path.insert(0,str(ROOT/'scripts'))
from schematic_layout.sexpr import parse,dump,first,all_nodes,value,form,Atom
from schematic_layout.scene import read_scene
from schematic_layout.scratch import require_scratch,scratch_base

def get(p):return json.loads(Path(p).read_text())
def put(p,x):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(argv,out,cwd=None,timeout=600):
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);t=time.monotonic();env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 try:q=subprocess.run(list(map(str,argv)),capture_output=True,text=True,cwd=cwd,env=env,timeout=timeout)
 except subprocess.TimeoutExpired as e:put(str(out)+'.command.json',{'argv':list(map(str,argv)),'status':'TIMEOUT','seconds':time.monotonic()-t});return -1
 Path(str(out)+'.stdout').write_text(q.stdout);Path(str(out)+'.stderr').write_text(q.stderr);put(str(out)+'.command.json',{'argv':list(map(str,argv)),'cwd':str(cwd) if cwd else None,'returncode':q.returncode,'seconds':time.monotonic()-t});return q.returncode

def assembly_flag(component,name):
 """KiCad XML exports fitted/exclusion flags as marker property nodes."""
 nodes=[x for x in component.findall('property') if x.get('name')==name]+component.findall(name)
 states=[]
 for x in nodes:
  raw=(x.get('value') if x.get('value') is not None else x.text or '').strip().lower()
  if raw in ('','yes','true','1'):states.append(True)
  elif raw in ('no','false','0'):states.append(False)
  else:raise ValueError('Unknown native assembly flag: '+name)
 if len(set(states))>1:raise ValueError('Conflicting native assembly flag: '+name)
 return bool(states and states[0])

def native(p):
 t=ET.parse(p).getroot();cs={}
 for c in t.findall('components/comp'):
  ref=c.get('ref');
  if ref.startswith('#'):continue
  cs[ref]={k:c.findtext(k,'') for k in ['value','footprint']}
  cs[ref].update({k:assembly_flag(c,k) for k in ['dnp','exclude_from_bom','exclude_from_board']})
  ls=c.find('libsource');cs[ref]['lib']=ls.attrib if ls is not None else None
  cs[ref]['MPN']={f.get('name'):f.text or '' for f in c.findall('fields/field')}.get('MPN')
 return {'identity_schema_version':2,'identity_scope':'value/footprint/MPN/libsource and native DNP/BOM/board exclusion flags; not arbitrary user fields or all library pin definitions','components':cs,'partitions':sorted([sorted(x.get('ref')+'.'+x.get('pin') for x in n.findall('node') if not x.get('ref').startswith('#')) for n in t.findall('nets/net') if any(not x.get('ref').startswith('#') for x in n.findall('node'))])}

def treehash(p):return {x.relative_to(p).as_posix():sha(x) for x in Path(p).rglob('*') if x.is_file() and '.git' not in x.parts and '__pycache__' not in x.parts}

def root_schematic(d):
 ss=list(Path(d).glob('*.kicad_sch'));return next((p for p in ss if all_nodes(parse(p.read_text()),'sheet')),ss[0] if ss else None)

def objpoints(tree):
 out={}
 for s in all_nodes(tree,'symbol'):
  ref=next((p[2] for p in all_nodes(s,'property') if p[1]=='Reference'),None);unit=value(s,'unit',1)
  if ref:
   k=f'{ref}:unit{unit}';at=first(s,'at');out[k]=list(map(float,at[1:3]))
   for f in all_nodes(s,'property'):
    if first(f,'at'):out[k+':'+f[1]]=list(map(float,first(f,'at')[1:3]))
 for n,w in enumerate(all_nodes(tree,'wire')):out[f'wire:{n}']=[list(map(float,p[1:3])) for p in all_nodes(first(w,'pts',[]),'xy')]
 scene=read_scene(tree)
 for n,(k,f) in enumerate(scene.labels):out[f'{k}:{n}:{f.text}']=[f.x,f.y]
 for sym in scene.symbols:
  for pin in sym.pins:out[pin.id]=list(pin.point);out['pin:'+pin.id]=list(pin.point)
 for n,p in enumerate(scene.junctions):out[f'junction:{n}']=list(p)
 for n,p in enumerate(scene.no_connects):out[f'nc:{n}']=list(p)
 return out

def verify(d,out):
 d=Path(d);root=root_schematic(d);intent=d/'electrical-intent.json'
 if not root or not intent.exists():return {'status':'NOT_RUN','reason':'Root or intent missing'}
 cmd=[PY,'-B',ROOT/'scripts/verify_schematic.py',root,'--intent',intent,'--out',out]
 contract=d/'reference-contract.json'
 if contract.exists():cmd+=['--reference-contract',contract]
 call(cmd,Path(out).parent/(Path(out).name+'-verify'),d)
 p=Path(out)/'summary.json';return get(p) if p.exists() else {'status':'NOT_RUN','reason':'Verifier did not write summary'}


def execution_provenance(out,mode):
 """Post-check real command ROOT and current pinned HEAD; never fabricate run-time hashes."""
 records=[];valid=True
 for p in Path(out).rglob('*.command.json'):
  c=get(p);argv=c.get('argv',[]);relevant=False;ok=False
  if mode=='delivery' and p.name.endswith('-execute.command.json'):
   relevant=True;ok='--asg'in argv and Path(argv[argv.index('--asg')+1]).resolve()==ROOT.resolve()
  if mode in ['overstrict','mutation']:
   target=['check_schematic_geometry.py','check_schematic_readability.py'] if mode=='overstrict' else ['verify_schematic.py']
   for x in argv:
    if Path(str(x)).name in target:
     relevant=True;ok=Path(x).resolve()==(ROOT/'scripts'/Path(x).name).resolve();break
  if relevant:records.append({'command':str(p),'sha256':sha(p),'root_matches':ok});valid=valid and ok
 return {'verified':bool(records) and valid,'repo':str(ROOT.resolve()),'postchecked_head':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'scope':'Command ROOT and current fixed HEAD verified after execution. Command files are original invocation records. No claim of a newly captured historical run-time source hash.','commands':records}
