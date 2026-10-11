from pathlib import Path
import runpy,json,sys,argparse
p=argparse.ArgumentParser();p.add_argument('--runner',type=Path,required=True);p.add_argument('--scratch',type=Path,required=True);a=p.parse_args();a.scratch.mkdir(parents=True,exist_ok=False)
mod=runpy.run_path(str(a.runner));locate=mod['locate_native_output'];rebuilt=mod['REBUILT_NATIVE_OUTPUTS'];frozen=mod['FROZEN_NATIVE_OUTPUTS'];checks=[]
for name in ['delivery','parent-control/delivery']:
 root=a.scratch/name
 for n,relative in rebuilt.items():
  actual=root/relative;actual.parent.mkdir(parents=True,exist_ok=True);actual.write_text('TRUE_NATIVE')
  checks.append({'case':f'parent-{name}-round{n:02}','pass':locate(root,n,rebuilt)==actual})
  out=actual.parents[1]
  decoys=[out/'delivery/native/netlist.xml',out/'runtime-asg/tests/fixtures/native/netlist.xml',out/'control-verification/netlist.xml',out/'copied-project/verify/netlist.xml']
  if n==1:decoys.append(out/'asg/native/netlist.xml')
  if n==9:decoys.append(out/'verify/netlist.xml')
  for d in decoys:d.parent.mkdir(parents=True,exist_ok=True);d.write_text('DECOY')
  checks.append({'case':f'decoys-present-{name}-round{n:02}','pass':locate(root,n,rebuilt)==actual})
  actual.unlink();checks.append({'case':f'missing-no-fallback-{name}-round{n:02}','pass':locate(root,n,rebuilt)is None})
for n,relative in frozen.items():
 root=a.scratch/'frozen-control';actual=root/relative;actual.parent.mkdir(parents=True,exist_ok=True);actual.write_text('FROZEN_NATIVE');checks.append({'case':f'frozen-exact-round{n:02}','pass':locate(root,n,frozen)==actual});actual.unlink()
 decoy=root/f'round-{n:02}/asg-delivery/copied/native/netlist.xml';decoy.parent.mkdir(parents=True,exist_ok=True);decoy.write_text('DECOY');checks.append({'case':f'frozen-missing-no-fallback-round{n:02}','pass':locate(root,n,frozen)is None})
checks.append({'case':'unknown-round','pass':locate(a.scratch,11,rebuilt)is None})
assert all(c['pass']for c in checks)
(a.scratch/'results.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2)+'\n');print(len(checks),'locator regression cases PASS')
