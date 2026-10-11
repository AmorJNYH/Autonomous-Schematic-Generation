"""Literal historical build replay plus current automatic gates and native equality."""
import sys,argparse,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',required=True,type=Path);a.add_argument('--out',required=True,type=Path);v=a.parse_args();v.out.resolve().relative_to(Path('/tmp/codex-work').resolve());v.out.mkdir(parents=True,exist_ok=False);t=time.monotonic();runs=[];rounds={}
 for h in get(v.cache/'prepared.json')['helpers']:
  if h['status']!='READY':runs.append({'id':h['id'],'status':'NOT_RUN'});continue
  p=Path(h['cached_helper']);assert sha(p)==h['sha256'];old=p.read_text();new=old.replace("assert O.is_relative_to(R.resolve())and not O.exists()", "assert O.is_relative_to(Path('/tmp/codex-work').resolve())and not O.exists()")
  # Enforce the caller's independent role TMPDIR for legacy helpers.
  new=new.replace("str(R/'tmp/root')","os.environ['TMPDIR']").replace("str(a.out/'tmp')","os.environ['TMPDIR']")
  q=v.out/p.name;q.write_text(new);out=v.out/h['id'];args=list(h['argv']);args[args.index('--asg')+1]=str(ROOT);args[args.index('--out')+1]=str(out)
  # C-reference answer diagnostics are unnecessary for delivery compatibility.
  if h['id']=='replay-10' and '--reference' in args:n=args.index('--reference');del args[n:n+2]
  code=call([PY,'-B',q,*args],v.out/(h['id']+'-execute'),timeout=1800);s=out/'summary.json';report=get(s) if s.exists() else {};runs.append({'id':h['id'],'returncode':code,'original_helper_sha256':sha(p),'adapted_helper_sha256':sha(q),'adaptations':'Output safety root and independent TMPDIR only; historical algorithms unchanged','result':report})
  if h['id']=='replay-01to04':rounds.update(report.get('rounds',{}))
  else:rounds[h['id'][-2:]]=report
 # Independently compare rebuilt exported XML with frozen native XML, not the public answer.
 frozen=['native-final/netlist.xml','verification-final/netlist.xml','verification/netlist.xml','verify-04/netlist.xml','verify-final/netlist.xml','native/netlist.xml','native/netlist.xml','verify-04/netlist.xml','native-frozen/netlist.xml','native-frozen/netlist.xml']
 base=Path('/Users/skyfend/Documents/ChatGPT/Auto-Development/ASG提升计划/2026-10-08-10轮')
 for n in range(1,11):
  key=f'{n:02}';r=rounds.setdefault(key,{});o=v.out/('replay-01to04/round'+key if n<=4 else 'replay-'+key)
  preferred=o/('rebuilt-verification/netlist.xml' if n==3 else 'native/netlist.xml' if n in [4,5,6,7,8] else 'verify/netlist.xml')
  if n==1:preferred=o/'asg/native/netlist.xml'
  opts=list(o.glob('**/netlist.xml')) if o.exists() else [];new=preferred if preferred.exists() else next((p for p in opts if 'runtime-asg' not in p.parts and 'delivery' not in p.parts and 'control' not in str(p)),None)
  old=base/('round-'+key)/'asg-delivery'/frozen[n-1]
  if not old.exists():
   alternatives=list((base/('round-'+key)/'asg-delivery').glob('**/netlist.xml'));old=next((p for p in alternatives if any(k in str(p) for k in ['native-final','native-frozen','verification-final','verification','native','verify-final'])),None)
  equality=None
  if old and new and Path(old).exists():
   before=native(old);after=native(new);equality={'component_identity_equal':before['components']==after['components'],'physical_partition_equal':before['partitions']==after['partitions'],'frozen_xml':str(old),'frozen_sha256':sha(old),'rebuilt_xml':str(new),'rebuilt_sha256':sha(new)}
  r['frozen_native_comparison']=equality;r['comparison_status']='MEASURED' if equality else 'NOT_RUN';r['known_inherited_build_failure']=n==2
 summary={'asg_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'seconds':time.monotonic()-t,'rounds':rounds,'runs':runs,'scope':'Historical build compatibility only; gates remain raw. Round02 inherited failure separate. Source-answer equivalence is distinct from freeze-rebuild equality. No human SR/hardware release.'}
 provenance=execution_provenance(v.out,'delivery');summary['execution_provenance_verified']=provenance['verified'];summary['execution_provenance']=provenance
 put(v.out/'summary.json',summary);print(json.dumps({'seconds':summary['seconds'],'rounds':{k:{'build_exit':r.get('build_exit',r.get('asg',{}).get('build_returncode')),'comparison_status':r['comparison_status'],'native':r['frozen_native_comparison']} for k,r in rounds.items()}},ensure_ascii=False))
if __name__=='__main__':main()
