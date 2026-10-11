"""Release guards compare preserved measured sets, never just aggregate ratios."""
import argparse,json
from pathlib import Path
from bench_common import get,put

def changed_engineering_inputs(row):
 # KiCad may create a new .kicad_prl UI/session cache during native verification/resume.
 # Never exclude a file present in the baseline; preserve raw records separately.
 return {k:v for k,v in row.get('changed_inputs',{}).items()if not(k.endswith('.kicad_prl')and v.get('before')is None)}

def compare(before,after,expected_before=None,expected_after=None):
 errors=[]
 if not expected_before or not expected_after:errors.append('EXPECTED_ASG_COMMITS_MISSING')
 for label,root,expected in [('before',before,expected_before),('after',after,expected_after)]:
  for suite in ['overstrict','mutation','delivery']:
   meta=get(root/suite/'summary.json')
   if meta.get('asg_commit')!=expected:errors.append('ASG_COMMIT_MISMATCH:'+label+':'+suite)
   if not meta.get('execution_provenance_verified'):errors.append('ASG_COMMAND_ROOT_UNVERIFIED:'+label+':'+suite)
 bs=get(before/'overstrict/summary.json');a=get(after/'overstrict/summary.json');bm=get(before/'overstrict/matrix.json');am={r['id']:r for r in get(after/'overstrict/matrix.json')}
 if not bs.get('benchmark_inputs_hash') or bs.get('benchmark_inputs_hash')!=a.get('benchmark_inputs_hash'):errors.append('OVERSTRICT_BENCHMARK_INPUTS_CHANGED_OR_MISSING')
 if len({r['id']for r in bm})!=len(bm):errors.append('OVERSTRICT_DUPLICATE_BASELINE_ROW_IDS')
 if len(am)!=len(get(after/'overstrict/matrix.json')):errors.append('OVERSTRICT_DUPLICATE_ROW_IDS')
 identity_fields=['source_repository','source_commit','page','gate','rule','objects','coordinates_mm']
 for row in bm:
  r=am.get(row['id'])
  if not r or any(k not in row or k not in r or row[k]!=r[k] for k in identity_fields):errors.append('OVERSTRICT_ROW_IDENTITY_CHANGED_OR_MISSING:'+row['id'])
 if not bs.get('report_execution_verified') or not a.get('report_execution_verified'):errors.append('OVERSTRICT_REPORT_EXECUTION_UNVERIFIED')
 if not a.get('source_cache_hash_verified'):errors.append('OVERSTRICT_SOURCE_CACHE_OR_REPORT_UNVERIFIED')
 for row in bm:
  if row['adjudication'] not in ['REAL','FALSE_POSITIVE'] or row['measurement_status']!='MEASURED':continue
  r=am.get(row['id'])
  if not r or r['adjudication']!=row['adjudication'] or r['measurement_status']!='MEASURED':errors.append('OVERSTRICT_MEASURED_SET_LOST:'+row['id']);continue
  if row['adjudication']=='REAL' and row['reported'] is True and r['reported'] is not True:errors.append('G2_REAL_LOST:'+row['id'])
 prior_inputs={r['round']:r['inputs']for r in get(before/'mutation/baseline.json')};new_inputs={r['round']:r['inputs']for r in get(after/'mutation/baseline.json')}
 if not prior_inputs or prior_inputs!=new_inputs:errors.append('MUTATION_BASELINE_INPUTS_CHANGED_OR_MISSING')
 mut_before=get(before/'mutation/matrix.json');mut_after={(r['round'],r['type']):r for r in get(after/'mutation/matrix.json')}
 if len({(r['round'],r['type'])for r in mut_before})!=len(mut_before) or len(mut_after)!=len(get(after/'mutation/matrix.json')):errors.append('MUTATION_DUPLICATE_ROW_KEYS')
 for row in mut_before:
  r=mut_after.get((row['round'],row['type']))
  if not r or row.get('plan')!=r.get('plan') or changed_engineering_inputs(row)!=changed_engineering_inputs(r):errors.append('MUTATION_PLAN_OR_CHANGED_INPUTS_CHANGED:'+row['round']+':'+row['type'])
  if row['status'] not in ['CAUGHT','MISSED']:continue
  r=mut_after.get((row['round'],row['type']))
  if not r or r['status'] not in ['CAUGHT','MISSED']:errors.append('MUTATION_MEASURED_SET_LOST:'+row['round']+':'+row['type'])
  elif row['status']=='CAUGHT' and r['status']!='CAUGHT':errors.append('G3_CAUGHT_REGRESSED:'+row['round']+':'+row['type'])
 old_delivery=get(before/'delivery/summary.json');new_delivery=get(after/'delivery/summary.json')
 old_helpers={r['id']:r.get('original_helper_sha256')for r in old_delivery['runs']};new_helpers={r['id']:r.get('original_helper_sha256')for r in new_delivery['runs']}
 if not old_helpers or old_helpers!=new_helpers or any(not h for h in old_helpers.values()):errors.append('DELIVERY_ORIGINAL_HELPERS_CHANGED_OR_MISSING')
 delivery=get(after/'delivery/summary.json')['rounds']
 for key,row in get(before/'delivery/summary.json')['rounds'].items():
  prior=row.get('frozen_native_comparison');new=delivery.get(key,{}).get('frozen_native_comparison')
  if prior is None and key=='02':continue
  if prior and new and (not prior.get('frozen_sha256') or prior.get('frozen_sha256')!=new.get('frozen_sha256')):errors.append('DELIVERY_FROZEN_BASELINE_CHANGED:'+key)
  if not prior or not new or not new.get('component_identity_equal') or not new.get('physical_partition_equal'):errors.append('DELIVERY_NATIVE_CHANGE_OR_MISSING:'+key)
 return {'status':'REJECT' if errors else 'AUTOMATIC_GUARDS_PASS','errors':errors,'G1_before':bs['G1']['reported'],'G1_after':a['G1']['reported'],'G2_before':bs['G2'],'G2_after':a['G2'],'scope':'Benchmark input fingerprint and per-row source/commit/page/gate/rule/objects/coordinates must remain identical. Mapping repair requires a separately versioned baseline. Measured sets must not shrink or become UNMAPPED. Missing source/report rejects. G2 retention, G3 catch retention and native equivalence guard only; no hardware or human-review approval.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--before',required=True,type=Path);p.add_argument('--after',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--before-commit',required=True);p.add_argument('--after-commit',required=True);a=p.parse_args();r=compare(a.before,a.after,a.before_commit,a.after_commit);put(a.out,r);print(json.dumps(r,ensure_ascii=False));return 1 if r['status']=='REJECT' else 0
if __name__=='__main__':raise SystemExit(main())
