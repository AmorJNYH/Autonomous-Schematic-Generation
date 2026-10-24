"""Regression checks for conflicting labels and missing source/report measurement."""
import sys,subprocess,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--scratch',required=True,type=Path);v=a.parse_args();v.scratch.mkdir(parents=True,exist_ok=False);here=Path(__file__).parent
 source=next(r for r in get(here/'labels.json')['labels'] if r['round']=='02' and r['rule']=='body_overlap' and Path(r['page'] or '').stem=='Dasduino COREPLUS');one=dict(source);two=dict(source,id=source['id']+'-conflict',adjudication='REAL' if source['adjudication']=='FALSE_POSITIVE' else 'FALSE_POSITIVE');put(v.scratch/'conflicting.json',{'labels':[one,two]})
 subprocess.run([PY,'-B',here/'prepare.py','--cache',v.scratch/'cache','--labels',v.scratch/'conflicting.json'],check=True,capture_output=True,text=True)
 prepared=get(v.scratch/'cache/prepared.json');assert len(prepared['labels'])==2 and all(r['mapping_status']=='UNMAPPED' and 'Conflicting' in r['mapping_reason'] for r in prepared['labels'])
 for s in prepared['sources']:s['status']='UNAVAILABLE'
 for r in prepared['labels']:r.update(mapping_status='MAPPED',adjudication='REAL',page='Dasduino COREPLUS.kicad_sch')
 put(v.scratch/'cache/prepared.json',prepared)
 subprocess.run([PY,'-B',here/'run.py','--cache',v.scratch/'cache','--out',v.scratch/'missing-report'],check=True,capture_output=True,text=True)
 result=get(v.scratch/'missing-report/summary.json');assert result['G2']['unmeasured']==2 and result['G2']['not_reported']==0
 put(v.scratch/'results.json',{'conflicting_same_object_labels':'PASS','unavailable_source_or_missing_report_unmeasured':'PASS'});print('2 boundary regressions PASS')
if __name__=='__main__':main()
