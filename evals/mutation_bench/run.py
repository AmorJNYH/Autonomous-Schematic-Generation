"""Single-fault matrix with gate deltas, object attribution and native probe validity."""
import sys,argparse,collections,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
from incremental_delivery import require_cache_revision
from run_binding import capture,open_run,validate_run
from operators import mutate,TYPES
from extra_operators import EXTRA_TYPES,mutate_extra,selected_types
from native_probe import probe_delta,attributable_name_errors
FILES={'intent_netlist':'intent-netlist.json','symbol_integrity':'symbol-integrity.json','hierarchy':'hierarchy.json','reference_contract':'reference-contract.json','external_supply':'external-supply.json','erc':'erc.json','readability':'readability.json'}
def entries(report,gate):
 out=[]
 def descend(v,path=''):
  if isinstance(v,dict):
   for k,x in v.items():
    if isinstance(x,list) and k in ['errors','failures','violations','findings','missing_pins','missing_components','hidden_physical_power_pins','hidden_pins','pin_name_mismatches','pin_map_errors','candidates','unnamed_pins']:
     out.extend({'path':path+'/'+k,'entry':a} for a in x)
    else:descend(x,path+'/'+k)
  elif isinstance(v,list):
   for i,x in enumerate(v):descend(x,path+'/'+str(i))
 descend(report);return out

def reports(out):
 out=Path(out);r={k:get(out/n) for k,n in FILES.items() if (out/n).exists()};r['geometry']={p.name:get(p) for p in (out/'geometry').glob('*.json')};return r

def new_entries(before,after,gate):
 a=collections.Counter(json.dumps(x,sort_keys=True,ensure_ascii=False) for x in entries(before.get(gate,{}),gate));b=collections.Counter(json.dumps(x,sort_keys=True,ensure_ascii=False) for x in entries(after.get(gate,{}),gate));return [json.loads(x) for x in (b-a).elements()]

def classify(bs,br,ms,mr,p,rec):
 kind=p['type']
 if rec.get('probe_kind')=='NOT_RUN':rec['status']='NOT_RUN';return
 if kind in EXTRA_TYPES and (rec.get('probe_kind')!='NAME_ONLY' or not rec.get('probe_valid')):
  rec['probe_valid']=False;rec['caught_by']=[];rec['status']='INVALID_PROBE';return
 if rec.get('probe_kind')=='NAME_ONLY':
  attributed=attributable_name_errors(rec['native_delta'],rec['new_errors'].get('intent_netlist',[]))
  rec['attributed_errors']={'intent_netlist':attributed}
  rec['caught_by']=['intent_netlist'] if ms.get('gates',{}).get('intent_netlist',{}).get('status')=='FAIL' and attributed else []
  rec['status']='CAUGHT' if rec['caught_by'] else 'MISSED'
  return
 for gate,g in ms.get('gates',{}).items():
  if g.get('status')!='FAIL':continue
  delta=rec['new_errors'].get(gate,[]);tokens=[str(x)for x in p.get('objects',[])];attributed=[z for z in delta if any(tok in json.dumps(z,ensure_ascii=False) for tok in tokens)]
  if gate=='readability':
   before=br.get(gate,{}).get('sheets',{}).get(p.get('file'),{});after=mr.get(gate,{}).get('sheets',{}).get(p.get('file'),{})
   if kind=='M-CROSS':attributed=[{'crossing_point':z} for z in after.get('crossing_points',[]) if z not in before.get('crossing_points',[]) and z in p.get('coordinates_mm',[])]
   elif kind=='M-TORTUOUS':attributed=[{'tortuous':z} for z in after.get('tortuous',[]) if z not in before.get('tortuous',[])]
  if gate=='hierarchy' and kind=='M-PAGE-MISSING':attributed=delta
  if bs.get('gates',{}).get(gate,{}).get('status')=='PASS' or attributed:
   rec['caught_by'].append(gate)
  rec.setdefault('attributed_errors',{})[gate]=attributed
 rec['status']='INVALID_PROBE' if not rec['probe_valid'] else 'CAUGHT' if rec['caught_by'] else 'MISSED'

def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--types',nargs='*');a.add_argument('--resume',action='store_true');a.add_argument('--revision',type=int,choices=[2,3],default=2);v=a.parse_args();
 try:types=selected_types(v.types,v.revision,TYPES)
 except ValueError as error:a.error(str(error))
 require_cache_revision(v.cache,v.revision);binding_receipt=open_run(v.out,capture(ROOT,v.cache,v.revision,types,'mutation'),v.resume);start=time.monotonic();matrix=get(v.out/'matrix.json') if v.resume and (v.out/'matrix.json').exists() else [];baseline=get(v.out/'baseline.json') if v.resume and (v.out/'baseline.json').exists() else [];metadata=get(v.out/'run-metadata.json') if (v.out/'run-metadata.json').exists() else {'start_epoch':getattr(v.out.stat(),'st_birthtime',time.time()),'resume_count':0};metadata['resume_count']+=int(v.resume);put(v.out/'run-metadata.json',metadata);code_hashes={p.name:sha(p)for p in Path(__file__).parent.glob('*.py')}
 for c in get(v.cache/'prepared.json')['circuits']:
  source=Path(c['cache']);assert treehash(source)==c['inputs'];r=v.out/c['round'];base=r/'baseline';d=base/'delivery';
  if c.get('functional_native')=='NOT_RUN':
   baseline=[b for b in baseline if b['round']!=c['round']];baseline.append({'round':c['round'],'summary':{'status':'NOT_RUN','reason':c['not_run_reason']},'inputs':c['inputs']});put(v.out/'baseline.json',baseline)
   matrix.extend({'round':c['round'],'type':kind,'status':'NOT_RUN','probe_kind':'NOT_RUN','reason':c['not_run_reason']} for kind in types if not any(row['round']==c['round'] and row['type']==kind for row in matrix));put(v.out/'matrix.json',matrix);continue
  if not d.exists():shutil.copytree(source,d)
  bs=get(base/'verify/summary.json') if v.resume and (base/'verify/summary.json').exists() else verify(d,base/'verify');br=reports(base/'verify');baseline=[b for b in baseline if b['round']!=c['round']];baseline.append({'round':c['round'],'summary':bs,'inputs':c['inputs']});put(v.out/'baseline.json',baseline)
  for kind in types:
   if any(r['round']==c['round'] and r['type']==kind for r in matrix):continue
   t=time.monotonic();out=r/kind;delivery=out/'delivery';
   if not delivery.exists():shutil.copytree(source,delivery)
   p=get(out/'predeclared-plan.json') if v.resume and (out/'predeclared-plan.json').exists() else (mutate_extra(delivery,kind) if kind in EXTRA_TYPES else mutate(delivery,kind));p['round']=c['round'];put(out/'predeclared-plan.json',p)
   rec={'round':c['round'],'type':kind,'plan':p,'status':p['status'],'baseline_gates':bs.get('gates',{}),'seconds':None}
   if p['status']!='APPLICABLE':rec['seconds']=time.monotonic()-t;matrix.append(rec);continue
   changed={k:{'before':c['inputs'].get(k),'after':sha(delivery/k)} for k in treehash(delivery) if c['inputs'].get(k)!=sha(delivery/k)};rec['changed_inputs']=changed;rec['intent_unchanged']=sha(delivery/'electrical-intent.json')==sha(source/'electrical-intent.json')
   if kind=='M-STALE':
    # A freshly generated native evidence snapshot, then stale source hash only.
    src=d;fresh=out/'freshness-probe-v2';shutil.copytree(src,fresh);ev=fresh/'bench-native-evidence';shutil.copytree(base/'verify',ev);inputs={k:h for k,h in treehash(fresh).items() if not k.startswith('bench-native-evidence/')};outputs={str(x.relative_to(fresh)):sha(x) for x in ev.rglob('*') if x.is_file()};geom=next((k for k in outputs if '/geometry/' in k),None)
    mf={'schema_version':1,'root':root_schematic(fresh).name,'inputs':inputs,'outputs':outputs,'roles':{'netlist':['bench-native-evidence/netlist.xml'],'erc':['bench-native-evidence/erc.json'],'render':['bench-native-evidence/schematic.pdf'],'geometry':[geom]if geom else []}};put(fresh/'freshness-manifest.json',mf)
    call([PY,'-B',ROOT/'scripts/check_delivery_freshness.py',fresh/'freshness-manifest.json'],out/'freshness-before');before=get(out/'freshness-before.stdout');root=root_schematic(fresh);root.write_text(root.read_text()+'\n');call([PY,'-B',ROOT/'scripts/check_delivery_freshness.py',fresh/'freshness-manifest.json'],out/'freshness-after');after=get(out/'freshness-after.stdout');rec.update(status='CAUGHT' if before['status']=='FRESH' and any(e.get('kind')=='changed_inputs' and e.get('path')==root.name for e in after['errors']) else 'INVALID_PROBE',baseline_freshness=before,mutant_freshness=after,caught_by=['freshness']if before['status']=='FRESH' else [],new_errors=after['errors'])
   else:
    ms=get(out/'verify/summary.json') if v.resume and (out/'verify/summary.json').exists() else verify(delivery,out/'verify');mr=reports(out/'verify');rec['mutant_gates']=ms.get('gates',{});rec['new_errors']={g:new_entries(br,mr,g) for g in set(br)|set(mr)};rec['caught_by']=[];rec['probe_valid']=True
    if kind in ['M-PIN-SWAP','M-NET-MERGE','M-PIN-FLOAT','M-NC-WRONG','M-GND-MERGE','M-VALUE'] or kind in EXTRA_TYPES:
     if (base/'verify/netlist.xml').exists() and (out/'verify/netlist.xml').exists():
      b=native(base/'verify/netlist.xml');m=native(out/'verify/netlist.xml');rec['native_delta']={'partitions_changed':b['partitions']!=m['partitions'],'identity_changed':b['components']!=m['components']};rec['probe_valid']=rec['native_delta']['identity_changed'] if kind=='M-VALUE' else rec['native_delta']['partitions_changed']
      if v.revision==3:
       rec['native_delta']=probe_delta(base/'verify/netlist.xml',out/'verify/netlist.xml',b['components'],m['components'],get(source/'electrical-intent.json'));rec['probe_kind']=rec['native_delta']['probe_kind'];rec['probe_valid']=rec['native_delta']['identity_changed'] if kind=='M-VALUE' else rec['native_delta']['partitions_changed'] or rec['probe_kind']=='NAME_ONLY'
       if kind in EXTRA_TYPES:rec['probe_valid']=rec['probe_kind']=='NAME_ONLY' and rec['intent_unchanged']
     else:
      rec['probe_valid']=False
      if v.revision==3:rec['probe_kind']='NOT_RUN'
    classify(bs,br,ms,mr,p,rec)
   rec['seconds']=time.monotonic()-t;matrix.append(rec);put(v.out/'matrix.json',matrix);print(c['round'],kind,rec['status'],flush=True)
  assert treehash(source)==c['inputs']
 summary={'asg_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'seconds':time.time()-metadata['start_epoch'],'last_invocation_seconds':time.monotonic()-start,'run_metadata':metadata,'execution_code_hashes':code_hashes,'counts':dict(collections.Counter(r['status']for r in matrix)),'per_type':{k:dict(collections.Counter(r['status']for r in matrix if r['type']==k))for k in list(TYPES)+[t for t in EXTRA_TYPES if t in types]},'scope':'Only applicable valid one-fault probes count. Inherited FAIL requires new target-specific error; PASS→FAIL records gate. Warnings never caught. Missing operator/topology/contract is OUT_OF_SCOPE; semantic non-fault is INVALID_PROBE.'};summary['run_binding']=validate_run(v.out,ROOT,v.cache,v.revision,types,'mutation',binding_receipt);summary['benchmark_revision']=v.revision;summary['probe_kinds']=dict(collections.Counter(r.get('probe_kind','LEGACY') for r in matrix));summary['incremental_input_fingerprint']=get(v.cache/'prepared.json').get('incremental_input_fingerprint');provenance=execution_provenance(v.out,'mutation');summary['execution_provenance_verified']=provenance['verified'];summary['execution_provenance']=provenance;put(v.out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
