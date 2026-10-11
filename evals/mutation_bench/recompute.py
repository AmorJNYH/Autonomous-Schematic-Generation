"""Re-score preserved native reports after a measurement-parser repair, no design edits."""
import sys,argparse,collections,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
from run import reports,new_entries,classify
from operators import TYPES

def main():
 a=argparse.ArgumentParser();a.add_argument('--run',required=True,type=Path);v=a.parse_args();v.run.resolve().relative_to(Path('/tmp/codex-work').resolve());rows=get(v.run/'matrix.json');old=get(v.run/'summary.json');put(v.run/'summary-before-measurement-parser-repair.json',old);native_hashes={str(p.relative_to(v.run)):sha(p) for p in v.run.glob('*/**/verify/*.json')};before={k:sha(v.run/k) for k in ['matrix.json','summary.json']};changes=[]
 for r in rows:
  if 'mutant_gates' not in r:continue
  d=v.run/r['round'];bs=get(d/'baseline/verify/summary.json');br=reports(d/'baseline/verify');out=d/r['type'];ms=get(out/'verify/summary.json');mr=reports(out/'verify');p=r['plan'];oldstatus=r['status'];r['new_errors']={g:new_entries(br,mr,g) for g in set(br)|set(mr)};r['caught_by']=[];classify(bs,br,ms,mr,p,r)
  if r['status']!=oldstatus:changes.append({'round':r['round'],'type':r['type'],'before':oldstatus,'after':r['status'],'reason':'Nested reference-contract failures were omitted from measurement extraction; native verifier report already contained them.'})
 assert native_hashes=={str(p.relative_to(v.run)):sha(p) for p in v.run.glob('*/**/verify/*.json')};put(v.run/'native-reports-sha256.json',native_hashes);put(v.run/'matrix.json',rows);old['counts']=dict(collections.Counter(r['status']for r in rows));old['per_type']={k:dict(collections.Counter(r['status']for r in rows if r['type']==k))for k in TYPES};old['measurement_parser_repair']={'before_report_sha256':before,'changes':changes,'native_verifier_rerun':False,'native_reports_unchanged':True};old['execution_code_hashes']={p.name:sha(p)for p in Path(__file__).parent.glob('*.py')};put(v.run/'summary.json',old);print(json.dumps(old['counts']))
if __name__=='__main__':main()
