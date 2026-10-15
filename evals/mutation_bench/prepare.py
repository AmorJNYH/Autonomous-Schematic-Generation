"""Cache exact frozen candidate inputs; never mutate the originals."""
import sys,argparse,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',required=True,type=Path);a.add_argument('--revision',type=int,choices=[2,3],default=2);v=a.parse_args();require_scratch(v.cache);entries=[]
 for s in get(Path(__file__).parent.parent/'overstrict_bench/sources.json')['sources']:
  original=Path(s['history_delivery']);d=v.cache/s['round'];d.mkdir(parents=True,exist_ok=True)
  for p in original.rglob('*'):
   if p.is_file() and (p.suffix in ['.kicad_sch','.kicad_sym','.kicad_pro','.pdf','.json','.md','.txt','.py'] or p.name=='sym-lib-table') and not any(n.startswith(('native','verify','verification','baseline','render')) for n in p.relative_to(original).parts[:-1]):
    q=d/p.relative_to(original);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
  if (d/'project').exists():
   for p in (d/'project').glob('*'):
    if p.is_file():shutil.copyfile(p,d/p.name)
  entries.append({'round':s['round'],'source_delivery':str(original),'cache':str(d),'inputs':treehash(d),'status':'READY' if root_schematic(d) else 'UNAVAILABLE'})
 extra=[]
 if v.revision==3:
  from incremental_delivery import prepare_incremental,working_copy,fingerprint
  extra=prepare_incremental(get(Path(__file__).parent.parent/'incremental_deliveries.json'),v.cache/'incremental-frozen')
  for e in extra:
   d=working_copy(e,v.cache/e['id']);entries.append({'round':e['id'],'source_delivery':e.get('source_directory',e.get('archive')),'cache':str(d),'inputs':treehash(d),'status':'READY','functional_native':e['functional_native'],'not_run_reason':e.get('not_run_reason'),'source_fingerprint':fingerprint([e])})
 put(v.cache/'prepared.json',{'circuits':entries,'benchmark_revision':v.revision,'incremental_input_fingerprint':fingerprint(extra) if extra else None});print(json.dumps({'ready':sum(x['status']=='READY' for x in entries)}))
if __name__=='__main__':main()
