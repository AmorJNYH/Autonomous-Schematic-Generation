"""Verify and cache audited historical replay helpers; input circuits stay outside Git."""
import sys,argparse,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',required=True,type=Path);a.add_argument('--revision',type=int,choices=[2,3],default=2);v=a.parse_args();v.cache.mkdir(parents=True,exist_ok=True);entries=[]
 for h in get(Path(__file__).parent/'sources.json')['helpers']:
  p=Path(h['path']);x=dict(h);x['status']='UNAVAILABLE'
  if not p.exists() and (v.cache/p.name).exists():p=v.cache/p.name
  if p.exists() and sha(p)==h['sha256']:
   q=v.cache/p.name;q.write_bytes(p.read_bytes());x['cached_helper']=str(q);x['status']='READY'
  entries.append(x)
 extra=[]
 if v.revision==3:
  from incremental_delivery import prepare_incremental,fingerprint
  extra=prepare_incremental(get(Path(__file__).parent.parent/'incremental_deliveries.json'),v.cache/'incremental-frozen')
 put(v.cache/'prepared.json',{'helpers':entries,'benchmark_revision':v.revision,'frozen_deliveries':extra,'incremental_input_fingerprint':fingerprint(extra) if extra else None,'dependency_note':'Helpers consume original frozen history paths and recursively cached native project sources. Local historical input cache must exist; NOT_RUN if absent. No remote source substitution.'});print(json.dumps({'ready':sum(x['status']=='READY' for x in entries)}))
if __name__=='__main__':main()
