"""Prepare fixed hash originals into a cache; normalize actual historical labels."""
import sys,argparse,shutil,urllib.request,tarfile,io,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',required=True,type=Path);a.add_argument('--labels',type=Path);v=a.parse_args();v.cache.resolve().relative_to(Path('/tmp/codex-work').resolve());here=Path(__file__).parent
 sources=get(here/'sources.json')['sources'];resolved=[];reports=[]
 for s in sources:
  d=v.cache/s['round'];d.mkdir(parents=True,exist_ok=True);loc=Path(s['local_original']);status='READY'
  for n,h in s['source_files'].items():
   p=loc/n
   if (d/n).exists() and sha(d/n)==h:continue
   if p.exists() and sha(p)==h:shutil.copyfile(p,d/n);continue
   # Recover from the exact pinned upstream commit; select by SHA256, never filename guess.
   archive=v.cache/(s['round']+'-upstream.tar.gz')
   try:
    if not archive.exists():
     url=s['repository'].replace('https://github.com/','https://codeload.github.com/')+'/tar.gz/'+s['commit']
     with urllib.request.urlopen(url,timeout=120) as response:archive.write_bytes(response.read())
    with tarfile.open(archive) as tar:
     found=False
     for member in tar:
      if member.isfile() and member.name.endswith('.kicad_sch'):
       payload=tar.extractfile(member).read()
       if hashlib.sha256(payload).hexdigest()==h:(d/n).write_bytes(payload);found=True;break
     if not found:status='UNAVAILABLE'
   except Exception as exc:status='UNAVAILABLE'
  for p in loc.glob('*.kicad_pro'):shutil.copyfile(p,d/p.name)
  contexts={p.name:objpoints(parse(p.read_text())) for p in d.glob('*.kicad_sch')}
  for row in get(v.labels or here/'labels.json')['labels']:
   if row['round']!=s['round']:continue
   r=dict(row);r['adjudication']=r.get('adjudication_preserved',r['adjudication']);candidates=list(contexts)
   if r['page']:
    candidates=[x for x in candidates if Path(x).stem==r['page'] or x==r['page']]
   elif isinstance(r.get('historical_entry'),dict):
    report=r['historical_entry'].get('report','')
    if report=='geometry-original-root.json':candidates=[s['original_root']]
    elif 'peripheral' in report.lower():candidates=[x for x in candidates if 'peripheral' in x.lower()]
   objs=r['objects']
   if objs:candidates=[x for x in candidates if all(o in contexts[x] for o in objs)]
   if len(candidates)==1 and r['rule'] and (objs or r['coordinates_mm']):
    r['page']=candidates[0];r['mapping_status']='MAPPED';r['coordinates_mm']=r['coordinates_mm'] or [contexts[candidates[0]][o] for o in objs]
   else:r['mapping_status']='UNMAPPED';r['mapping_reason']='Missing rule/point, unresolved or ambiguous page/object binding';r['adjudication_preserved']=r['adjudication'];r['adjudication']='UNMAPPED'
   resolved.append(r)
  reports.append({'round':s['round'],'status':status,'files':{p.name:sha(p)for p in d.glob('*.kicad_sch')},'source':s})
 groups=collections.defaultdict(list)
 for row in resolved:
  if row['mapping_status']=='MAPPED' and row['gate']=='geometry':groups[(row['round'],row['page'],row['rule'],tuple(sorted(row['objects'])))].append(row)
 for key,rs in groups.items():
  verdicts={r['adjudication'] for r in rs};anchors={json.dumps(r['historical_entry'].get('source_coordinates'),sort_keys=True) for r in rs if r['historical_entry'].get('source_coordinates')}
  for r in rs:
   r['same_key_historical_rows']=len(rs)
   if len(verdicts)>1 or len(anchors)>1:
    r['mapping_status']='UNMAPPED';r['adjudication_preserved']=r['adjudication'];r['adjudication']='UNMAPPED';r['mapping_reason']='Conflicting adjudications or distinct coordinate entities share one current rule/object key; cannot distinguish current finding'
   elif len(rs)>1:r['count_scope']='Duplicate identical-adjudication historical gate rows retained as raw diagnostic units, not unique defects'
 put(v.cache/'prepared.json',{'sources':reports,'labels':resolved});print(json.dumps({'labels':len(resolved),'mapped':sum(r['mapping_status']=='MAPPED' for r in resolved),'sources':len(reports)}))
if __name__=='__main__':main()
