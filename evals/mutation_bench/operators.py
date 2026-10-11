"""Single isolated faults. Preconditions are explicit; no approximate probes."""
import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
TYPES={'M-PIN-SWAP':'intent_netlist','M-NET-MERGE':'intent_netlist','M-PIN-FLOAT':'intent_netlist','M-NC-WRONG':'intent_netlist','M-GND-MERGE':'intent_netlist','M-VALUE':'intent_netlist','M-SYM-PIN':'symbol_integrity','M-PIN-HIDDEN':'symbol_integrity','M-CROSS':'readability','M-TORTUOUS':'readability','M-OVERLAP':'geometry','M-WIRE-THRU':'geometry','M-OFFGRID':'geometry','M-PAGE-MISSING':'hierarchy','M-STALE':'freshness','M-PIN-NAME':'reference_contract','M-EXT-SUPPLY':'external_supply'}
def walk(t):
 for n in t:
  if isinstance(n,list):yield n;yield from walk(n)
def prop(s,name):return next((p for p in all_nodes(s,'property') if p[1]==name),None)
def mutate(d,kind):
 counter=[0]
 def fresh_uuid():
  counter[0]+=1;return str(uuid.uuid5(uuid.NAMESPACE_URL,kind+':'+str(counter[0])))
 roots=sorted(d.glob('*.kicad_sch'));parsed=[(p,parse(p.read_text())) for p in roots];plan={'type':kind,'expected_gate':TYPES[kind],'expected_status':'FAIL','status':'OUT_OF_SCOPE','reason':'Required topology/contract/operator precondition absent'}
 if kind=='M-PAGE-MISSING':
  for p,t in parsed:
   ss=all_nodes(t,'sheet')
   if ss:
    target=ss[0];plan.update(status='APPLICABLE',file=p.name,objects=[str(value(target,'uuid'))],before=copy.deepcopy(target),after=None);t.remove(target);p.write_text(dump(t)+'\n');return plan
  return plan
 if kind=='M-STALE':
  p=root_schematic(d);p.write_text(p.read_text()+'\n');return dict(plan,status='APPLICABLE',file=p.name,objects=[p.name],before='Original file SHA256',after='Extra trailing newline; semantic content unchanged')
 if kind=='M-GND-MERGE':
  labels=[(p,t,s,prop(s,'Value')) for p,t in parsed for s in all_nodes(t,'symbol') if prop(s,'Value') is not None and 'GND' in str(prop(s,'Value')[2]).upper()];names=list(dict.fromkeys(z[3][2] for z in labels))
  if len(names)<2:return plan
  p,t,s,v=next(z for z in labels if z[3][2]==names[1]);before=v[2];v[2]=names[0];p.write_text(dump(t)+'\n');return dict(plan,status='APPLICABLE',file=p.name,objects=[prop(s,'Reference')[2]],before=before,after=v[2])
 for p,t in sorted(parsed,key=lambda z:-len(all_nodes(z[1],'symbol'))):
  syms=all_nodes(t,'symbol');physical=[s for s in syms if prop(s,'Reference') is not None and not str(prop(s,'Reference')[2]).startswith('#')];scene=read_scene(t);ics=[s for s in physical if str(prop(s,'Reference')[2]).startswith('U')];passives=[s for s in physical if str(prop(s,'Reference')[2]).startswith(('R','C'))];s=next(iter(ics or physical),None)
  if not s:continue
  ref=prop(s,'Reference')[2];scene_s=next((q for q in scene.symbols if q.ref==ref),None)
  if kind in ['M-PIN-SWAP','M-NET-MERGE']:
   ls=all_nodes(t,'label')+all_nodes(t,'global_label');unique=[]
   for z in ls:
    if z[1] not in [x[1] for x in unique]:unique.append(z)
   if len(unique)<2:continue
   a,b=unique[:2];before=[a[1],b[1]];a[1]=b[1]
   if kind=='M-PIN-SWAP':b[1]=before[0]
   else:plan['expected_gate']='intent_netlist'
   plan.update(status='APPLICABLE',file=p.name,objects=before,before=before,after=[a[1],b[1]],coordinates_mm=[list(map(float,first(z,'at')[1:3]))for z in [a,b]],operator_scope='Two distinct connected named nets; label swap operator does not claim exact IC-adjacent pins')
  elif kind=='M-VALUE':
   if not passives:continue
   s=passives[0];ref=prop(s,'Reference')[2];intent=get(d/'electrical-intent.json');v=prop(s,'Value')
   # Explicit component identity is a precondition, never inferred from drawings.
   text=json.dumps(intent,ensure_ascii=False)
   if str(ref) not in text or str(v[2]) not in text:return dict(plan,reason='Intent lacks explicit chosen component value identity')
   before=v[2];v[2]='9.99G';plan.update(status='APPLICABLE',file=p.name,objects=[ref],before=before,after=v[2])
  elif kind in ['M-OVERLAP','M-OFFGRID']:
   if kind=='M-OVERLAP':
    target=next((z for z in physical if z is not s),None)
    if target is None:continue
    target_at=first(target,'at');at=first(s,'at');dx=float(target_at[1])-float(at[1]);dy=float(target_at[2])-float(at[2]);other=prop(target,'Reference')[2]
   else:dx,dy=.3,0;other=None
   before=copy.deepcopy(first(s,'at'))
   for holder in [s,*all_nodes(s,'property')]:
    at=first(holder,'at')
    if at:at[1]=float(at[1])+dx;at[2]=float(at[2])+dy
   plan.update(status='APPLICABLE',file=p.name,objects=[str(ref)]+([str(other)]if other else []),before=before,after=first(s,'at'))
  elif kind in ['M-PIN-FLOAT','M-NC-WRONG']:
   pin=next((x for x in (scene_s.pins if scene_s else []) if x.kind=='power_in'),None)
   if not pin:continue
   wires=[w for w in all_nodes(t,'wire') if any(tuple(map(float,q[1:3]))==tuple(pin.point) for q in all_nodes(first(w,'pts',[]),'xy'))]
   if not wires:continue
   for w in wires:t.remove(w)
   if kind=='M-NC-WRONG':t.append(form('no_connect',form('at',*pin.point),form('uuid',fresh_uuid())))
   plan.update(status='APPLICABLE',file=p.name,objects=[str(ref),pin.id],coordinates_mm=[list(pin.point)],before=copy.deepcopy(wires),after='deleted incident wire(s)'+(' and inserted no_connect' if kind=='M-NC-WRONG' else ''))
  elif kind in ['M-SYM-PIN','M-PIN-HIDDEN','M-PIN-NAME']:
   cache=first(t,'lib_symbols',[]);lib=next((z for z in all_nodes(cache,'symbol') if z[1]==value(s,'lib_id')),None)
   if lib is None:continue
   pins=[z for z in walk(lib) if z and z[0]=='pin' and first(z,'number') is not None]
   if kind=='M-SYM-PIN':
    nums=[]
    for z in pins:
     if value(z,'number') not in [value(x,'number') for x in nums]:nums.append(z)
    if len(nums)<2:continue
    before=[value(z,'number')for z in nums[:2]]
    for z in pins:
     n=first(z,'number')
     if n[1] in before:n[1]=before[1-before.index(n[1])]
    plan.update(status='APPLICABLE',file=p.name,objects=[str(ref)],before=before,after=before[::-1])
   else:
    z=next((z for z in pins if z[1]=='power_in'),None) if kind=='M-PIN-HIDDEN' else next((z for z in pins if z[1] not in ['power_in','power_out'] and scene_s and any(pin.id.endswith('.'+str(value(z,'number'))) and any(tuple(pin.point)==tuple(map(float,q[1:3])) for w in all_nodes(t,'wire') for q in all_nodes(first(w,'pts',[]),'xy')) for pin in scene_s.pins)),None)
    if z is None:continue
    before=copy.deepcopy(z)
    if kind=='M-PIN-HIDDEN':z.append(form('hide',Atom('yes')))
    else:
     if not (d/'reference-contract.json').exists():return dict(plan,reason='No reference contract supplied; pin names are diagnostic only')
     first(z,'name')[1]=''
    plan.update(status='APPLICABLE',file=p.name,objects=[str(ref)],pin=str(value(z,'number')),before=before,after=z)
  elif kind=='M-EXT-SUPPLY':
   outpin=next((x for q in scene.symbols if q.ref.startswith('U') for x in q.pins if x.kind=='power_out'),None);flag=next((z for z in syms if str(value(z,'lib_id')).endswith('PWR_FLAG')),None)
   if not outpin or not flag:continue
   z=copy.deepcopy(flag);before=copy.deepcopy(first(z,'at'));at=first(z,'at');dx=outpin.point[0]-float(at[1]);dy=outpin.point[1]-float(at[2]);at[1:3]=list(outpin.point)
   for f in all_nodes(z,'property'):
    q=first(f,'at')
    if q:q[1]=float(q[1])+dx;q[2]=float(q[2])+dy
   for q in walk(z):
    if q[0]=='uuid':q[1]=fresh_uuid()
    if q[0]=='reference':q[1]='#FLG0999'
   prop(z,'Reference')[2]='#FLG0999';t.append(z);plan.update(status='APPLICABLE',file=p.name,objects=[outpin.id.split('.')[0],'#FLG0999'],coordinates_mm=[list(outpin.point)],before=None,after='PWR_FLAG on board power_out pin')
  elif kind in ['M-CROSS','M-TORTUOUS','M-WIRE-THRU']:
   def wire(a,b):return form('wire',form('pts',form('xy',*a),form('xy',*b)),form('stroke',form('width',0),form('type',Atom('default'))),form('uuid',fresh_uuid()))
   if kind=='M-CROSS':
    # Clear grid region: two isolated distinct nets crossing without junction.
    center=(20.32,20.32);points=[((13.97,20.32),(26.67,20.32)),((20.32,13.97),(20.32,26.67))]
    for a,b in points:t.append(wire(a,b))
    plan.update(status='APPLICABLE',file=p.name,objects=['injected-crossing'],coordinates_mm=[list(center)],before=None,after=points)
   elif kind=='M-WIRE-THRU':
    body=next((q for q in scene.symbols if q.body and q.ref==ref),None)
    if not body:continue
    b=body.body;yy=(b.y_min+b.y_max)/2;a=(b.x_min-2.54,yy);z=(b.x_max+2.54,yy);t.append(wire(a,z));plan.update(status='APPLICABLE',file=p.name,objects=[str(ref)],coordinates_mm=[list(a),list(z)],before=None,after='Foreign wire across body')
   else:
    # Two-terminal isolated path with five elbows; free ends are explicit labels.
    pts=[(13.97,20.32),(13.97,25.4),(19.05,25.4),(19.05,30.48),(24.13,30.48),(24.13,35.56),(29.21,35.56)]
    for a,b in zip(pts,pts[1:]):t.append(wire(a,b))
    for name,xy in [('MUT_START',pts[0]),('MUT_END',pts[-1])]:t.append(form('label',name,form('at',*xy,0),form('effects',form('font',form('size',1.27,1.27)),form('justify',Atom('left'),Atom('bottom'))),form('uuid',fresh_uuid())))
    plan.update(status='APPLICABLE',file=p.name,objects=['MUT_START','MUT_END'],coordinates_mm=[list(z)for z in pts],before=None,after='Five-bend labelled two-terminal path')
  else:continue
  p.write_text(dump(t)+'\n');return plan
 return plan
