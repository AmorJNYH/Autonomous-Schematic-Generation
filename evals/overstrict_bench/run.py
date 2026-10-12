"""G1/G2 from exact per-item labels. Missing mappings are coverage gaps."""
import sys,argparse,collections,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
from run_binding import capture,open_run,validate_run
def valid_report(p,rc,page,kind):
 if not p.exists():return {}
 try:r=get(p)
 except (ValueError,TypeError):return {}
 if not isinstance(r,dict) or r.get('status') not in (['PASS','FAIL','INSUFFICIENT'] if kind=='geometry' else ['PASS','FAIL']) or rc!=(0 if r['status']=='PASS' else 2):return {}
 if kind=='geometry':
  if not isinstance(r.get('counts'),dict) or not isinstance(r.get('coverage'),dict) or not isinstance(r['coverage'].get('checks'),list):return {}
  f=r.get('findings')
  return r if isinstance(f,list) and all(isinstance(x,dict) and isinstance(x.get('code'),str) and isinstance(x.get('objects'),list) and isinstance(x.get('severity'),str) for x in f) else {}
 sheet=r.get('sheets',{}).get(page,{})
 gate=sheet.get('gate',{})
 if gate.get('status')!=r['status'] or gate.get('status') not in ['PASS','FAIL'] or not isinstance(gate.get('reasons'),list):return {}
 if any(not isinstance(sheet.get(k),list) for k in ['crossing_points','tortuous']):return {}
 return sheet

def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',type=Path,required=True);a.add_argument('--out',type=Path,required=True);v=a.parse_args();v.out.resolve().relative_to(Path('/tmp/codex-work').resolve());binding_receipt=open_run(v.out,capture(ROOT,v.cache,2,[],'overstrict'));t=time.monotonic();data=get(v.cache/'prepared.json');checks={};results=[]
 for s in data['sources']:
  d=v.cache/s['round'];reports={}
  if s['status']!='READY' or any(not (d/n).exists() or sha(d/n)!=h for n,h in s['source']['source_files'].items()):checks[s['round']]={};continue
  for p in d.glob('*.kicad_sch'):
   o=v.out/s['round'];o.mkdir(exist_ok=True);g=o/(p.stem+'-geometry.json');r=o/(p.stem+'-readability.json')
   gc=call([PY,'-B',ROOT/'scripts/check_schematic_geometry.py',p,'--output',g],o/(p.stem+'-geometry'))
   rc=call([PY,'-B',ROOT/'scripts/check_schematic_readability.py',p,'--out',r],o/(p.stem+'-readability'))
   reports[p.name]={'geometry':valid_report(g,gc,p.name,'geometry'),'readability':valid_report(r,rc,p.name,'readability')}
  checks[s['round']]=reports
 for row in data['labels']:
  r={k:v for k,v in row.items() if k!='historical_entry'};rep=checks.get(row['round'],{}).get(row['page'],{});observed=None
  if row['mapping_status']=='MAPPED' and rep.get(row['gate']):
   if row['gate']=='geometry':
    observed=any(x.get('code')==row['rule'] and sorted(x.get('objects',[]))==sorted(row['objects']) for x in rep.get('geometry',{}).get('findings',[])) if rep.get('geometry') else None
    if rep.get('geometry',{}).get('status')=='INSUFFICIENT' and observed is False:observed=None;r['measurement_reason']='INSUFFICIENT geometry coverage cannot support negative observation'
   else:
    coords=row['coordinates_mm'];coords=[coords] if coords and isinstance(coords[0],(int,float)) else coords
    if row['rule']=='tortuous_connection':observed=any(sorted(p)==sorted(row['objects']) for p in rep.get('readability',{}).get('tortuous',[]))
    if row['rule']=='wire_crossing':observed=any(any(len(p)==2 and len(c)==2 and max(abs(float(p[n])-float(c[n])) for n in range(2))<1e-4 for c in (coords or [])) for p in rep.get('readability',{}).get('crossing_points',[]))
  r['reported']=observed;r['measurement_status']='MEASURED' if observed is not None else 'UNMAPPED';results.append(r)
 counts={}
 for k in ['FALSE_POSITIVE','REAL','WARNING','INSUFFICIENT','UNMAPPED']:
  rs=[r for r in results if r['adjudication']==k];counts[k]={'labels':len(rs),'reported':sum(r['reported'] is True for r in rs),'not_reported':sum(r['reported'] is False for r in rs),'unmeasured':sum(r['reported'] is None for r in rs)}
 input_payload={'source_registry':get(Path(__file__).with_name('sources.json')),'prepared_sources':[{k:x[k] for k in ['round','status','source']} for x in data['sources']],'prepared_labels':[{k:v for k,v in x.items() if k!='historical_entry'} for x in data['labels']]}
 benchmark_inputs_hash=hashlib.sha256(json.dumps(input_payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 report_verified=all(all(bool(report.get(k))for k in ['geometry','readability']) for pages in checks.values()for report in pages.values()) and all(bool(checks.get(x['round']))for x in data['sources'])
 summary={'report_execution_verified':report_verified,'measured_repo':str(ROOT.resolve()),'benchmark_inputs_hash':benchmark_inputs_hash,'asg_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'seconds':time.monotonic()-t,'source_cache_hash_verified':all(s['status']=='READY' and all((v.cache/s['round']/n).exists() and sha(v.cache/s['round']/n)==h for n,h in s['source']['source_files'].items()) for s in data['sources']),'G1':counts['FALSE_POSITIVE'],'G2':counts['REAL'],'counts':counts,'unmapped_disposition_breakdown':dict(collections.Counter(r.get('adjudication_preserved',r['adjudication']) for r in results if r['measurement_status']=='UNMAPPED')),'per_round':{s['round']:dict(collections.Counter(r['measurement_status'] for r in results if r['round']==s['round'])) for s in data['sources']},'scope':'Exact historical rule/object or readability point identity; no alias guessing. A absent old rule is not proof of visually improved readability. WARNING/INSUFFICIENT separate. Geometric/readability duplicate gate rows not merged into root count.'}
 summary['run_binding']=validate_run(v.out,ROOT,v.cache,2,[],'overstrict',binding_receipt)
 provenance=execution_provenance(v.out,'overstrict');summary['execution_provenance_verified']=provenance['verified'];summary['execution_provenance']=provenance
 put(v.out/'matrix.json',results);put(v.out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
