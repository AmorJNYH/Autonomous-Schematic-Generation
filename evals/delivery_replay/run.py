"""Literal historical build replay plus current automatic gates and native equality."""
import sys,argparse,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bench_common import *
from incremental_delivery import require_cache_revision
from run_binding import capture,open_run,validate_run
# Exact outputs of the audited historical helpers; relative to suite/base roots.
# Parent directory names never determine whether an XML is native evidence.
REBUILT_NATIVE_OUTPUTS={
 1:'replay-01to04/round01/native/netlist.xml',
 2:'replay-01to04/round02/verify/netlist.xml',
 3:'replay-01to04/round03/rebuilt-verification/netlist.xml',
 4:'replay-01to04/round04/native/netlist.xml',
 5:'replay-05/native/netlist.xml',6:'replay-06/native/netlist.xml',
 7:'replay-07/native/netlist.xml',8:'replay-08/native/netlist.xml',
 9:'replay-09/native/netlist.xml',10:'replay-10/verify/netlist.xml'}
FROZEN_NATIVE_OUTPUTS={
 1:'round-01/asg-delivery/native-final/netlist.xml',
 2:'round-02/asg-delivery/verification-final/netlist.xml',
 3:'round-03/asg-delivery/verification/netlist.xml',
 4:'round-04/asg-delivery/verify-04/netlist.xml',
 5:'round-05/asg-delivery/verify-final/netlist.xml',
 6:'round-06/asg-delivery/native/netlist.xml',
 7:'round-07/asg-delivery/native/03/netlist.xml',
 8:'round-08/asg-delivery/verify-04/netlist.xml',
 9:'round-09/asg-delivery/native-v4/netlist.xml',
 10:'round-10/asg-delivery/native-frozen/netlist.xml'}

def locate_native_output(root,round_number,outputs):
 """Accept only the fixed helper/frozen output, never copied CAD or test fixtures."""
 relative=outputs.get(round_number)
 if relative is None:return None
 candidate=Path(root)/relative
 return candidate if candidate.is_file() else None

def main():
 a=argparse.ArgumentParser();a.add_argument('--cache',required=True,type=Path);a.add_argument('--out',required=True,type=Path);a.add_argument('--revision',type=int,choices=[2,3],default=2);v=a.parse_args();require_cache_revision(v.cache,v.revision);v.out.resolve().relative_to(Path('/tmp/codex-work').resolve());binding_receipt=open_run(v.out,capture(ROOT,v.cache,v.revision,[],'delivery'));t=time.monotonic();runs=[];rounds={}
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
 base=Path('/Users/skyfend/Documents/ChatGPT/Auto-Development/ASG提升计划/2026-10-08-10轮')
 for n in range(1,11):
  key=f'{n:02}';r=rounds.setdefault(key,{})
  new=locate_native_output(v.out,n,REBUILT_NATIVE_OUTPUTS)
  old=locate_native_output(base,n,FROZEN_NATIVE_OUTPUTS)
  equality=None
  if old and new and Path(old).exists():
   before=native(old);after=native(new);equality={'component_identity_equal':before['components']==after['components'],'physical_partition_equal':before['partitions']==after['partitions'],'frozen_xml':str(old),'frozen_sha256':sha(old),'rebuilt_xml':str(new),'rebuilt_sha256':sha(new)}
  r['frozen_native_comparison']=equality;r['comparison_status']='MEASURED' if equality else 'NOT_RUN';r['known_inherited_build_failure']=n==2
 extra={}
 if v.revision==3:
  from incremental_delivery import replay_frozen
  extra=replay_frozen(get(v.cache/'prepared.json').get('frozen_deliveries',[]),v.out/'incremental',verify,native);rounds.update(extra)
 summary={'benchmark_revision':v.revision,'incremental_input_fingerprint':get(v.cache/'prepared.json').get('incremental_input_fingerprint'),'incremental_sources':list(extra),'asg_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'seconds':time.monotonic()-t,'rounds':rounds,'runs':runs,'scope':'Historical build compatibility only; gates remain raw. Round02 inherited failure separate. Source-answer equivalence is distinct from freeze-rebuild equality. No human SR/hardware release.'}
 summary['run_binding']=validate_run(v.out,ROOT,v.cache,v.revision,[],'delivery',binding_receipt)
 provenance=execution_provenance(v.out,'delivery');summary['execution_provenance_verified']=provenance['verified'];summary['execution_provenance']=provenance
 if v.revision==3:
  incremental_provenance=execution_provenance(v.out/'incremental','mutation')
  summary['incremental_execution_provenance']=incremental_provenance
  summary['execution_provenance_verified']=summary['execution_provenance_verified'] and incremental_provenance['verified']
 put(v.out/'summary.json',summary);print(json.dumps({'seconds':summary['seconds'],'rounds':{k:{'build_exit':r.get('build_exit',r.get('asg',{}).get('build_returncode')),'comparison_status':r['comparison_status'],'native':r['frozen_native_comparison']} for k,r in rounds.items()}},ensure_ascii=False))
if __name__=='__main__':main()
