from pathlib import Path
import sys,copy,json,subprocess,uuid,xml.etree.ElementTree as ET,hashlib
R=Path(__file__).resolve().parents[3];sys.path[:0]=[str(R/'scripts'),str(R/'tests/fixtures/drawing')]
import recipe_board
from schematic_layout.sexpr import all_nodes,first,value,form,Atom,dump
from schematic_layout.native import find_cli,compare_netlist
from schematic_layout.net_name_origin import audit_name_origins,net_groups
import argparse
a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);args=a.parse_args();O=args.output;O.mkdir(parents=True,exist_ok=True);CLI=find_cli();base,_=recipe_board.draw().build('probe')
uid=lambda: str(uuid.uuid4())
def manual(node,name,kind='global_label'):
 label=next(n for n in all_nodes(node,'global_label') if n[1]=='MCU_DP');label[1]=name
 if kind=='label':label[0]=Atom('label');label.remove(first(label,'shape'))
 elif kind=='hierarchical_label':label[0]=Atom(kind)
 return label

def hierarchy(child,instances):
 puid=uid(); parent=form('kicad_sch',form('version',Atom('20250114')),form('generator','eeschema'),form('uuid',puid),form('paper','A4'),form('lib_symbols'),form('sheet_instances',form('path','/',form('page','1'))))
 for symbol in all_nodes(child,'symbol'):symbol.remove(first(symbol,'instances'));symbol.append(form('instances',form('project','probe')))
 for i in range(instances):
  suid=uid(); y=40+i*40; parent.append(form('sheet',form('at',20,y),form('size',20,20),form('uuid',suid),form('property','Sheetname','Stage'+str(i),form('at',20,y,0),form('effects',form('font',form('size',1.27,1.27)))),form('property','Sheetfile','child.kicad_sch',form('at',20,y+20,0),form('effects',form('font',form('size',1.27,1.27)))),form('pin','Net-(U9-SDO/SAO)',Atom('bidirectional'),form('at',20,y+10,180),form('effects',form('font',form('size',1.27,1.27))),form('uuid',uid())),form('instances',form('project','probe',form('path','/'+puid,form('page',str(i+2)))))))
  for symbol in all_nodes(child,'symbol'):
   ref=next(p[2] for p in all_nodes(symbol,'property') if p[1]=='Reference');ref=ref if not i else ref.rstrip('0123456789')+str(int(''.join(c for c in ref if c.isdigit()))+100)
   first(first(symbol,'instances'),'project').append(form('path','/'+puid+'/'+suid,form('reference',ref),form('unit',value(symbol,'unit',1))))
 return parent
records=[]
cases=['global-manual','local-manual','hierarchical','multiinstance','automatic-slash','power-manual','hidden-power-manual','encoded-unknown','variable-unknown','bus-unknown','stale-xml']
for tag in cases:
 out=O/tag;out.mkdir(parents=True,exist_ok=True);node=copy.deepcopy(base);files={}
 if tag in ('global-manual','local-manual','hierarchical','multiinstance','stale-xml'):
  manual(node,'Net-(U9-SDO/SAO)','label' if tag=='local-manual' else 'hierarchical_label' if tag in ('hierarchical','multiinstance') else 'global_label')
 elif tag=='automatic-slash':
  node.remove(next(n for n in all_nodes(node,'global_label') if n[1]=='MCU_DP'))
  for lib in all_nodes(first(node,'lib_symbols'),'symbol'):
   if lib[1]=='Device:R':
    for unit in all_nodes(lib,'symbol'):
     for pin in all_nodes(unit,'pin'):
      if value(pin,'number')=='1':first(pin,'name')[1]='SDO/SAO'
 elif tag=='power-manual':
  for symbol in all_nodes(node,'symbol'):
   if value(symbol,'lib_id')=='power:GND':
    next(p for p in all_nodes(symbol,'property') if p[1]=='Value')[2]='Net-(POWER-SDO/SAO)'
 elif tag=='hidden-power-manual':
  node[:]=[n for n in node if not isinstance(n,list) or n[0] not in ('label','global_label','hierarchical_label') and not (n[0]=='symbol' and str(value(n,'lib_id','')).startswith('power:'))]
  for lib in all_nodes(first(node,'lib_symbols'),'symbol'):
   if lib[1]=='Device:R':
    for unit in all_nodes(lib,'symbol'):
     for pin in all_nodes(unit,'pin'):
      if value(pin,'number')=='1':pin[1]=Atom('power_in');pin.append(Atom('hide'));first(pin,'name')[1]='Net-(HIDDEN-SDO/SAO)'
 elif tag=='encoded-unknown':manual(node,'A{slash}B')
 elif tag=='variable-unknown':manual(node,'${VAR}')
 elif tag=='bus-unknown':node.append(form('bus_alias','X',form('members','A','B')))
 if tag in ('hierarchical','multiinstance'):
  child=node;node=hierarchy(child,2 if tag=='multiinstance' else 1);files['child.kicad_sch']=child
 files['probe.kicad_sch']=node
 for name,tree in files.items():(out/name).write_text(dump(tree)+'\n')
 xml=out/'native.xml';argv=[CLI,'sch','export','netlist','--format','kicadxml','-o',str(xml),str(out/'probe.kicad_sch')];run=subprocess.run(argv,capture_output=True,text=True)
 rec={'tag':tag,'command':{'argv':argv,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr}}
 if run.returncode:rec['status']='NOT_RUN';records.append(rec);print(tag,'EXPORT_FAIL');continue
 if tag=='stale-xml':
  fresh=ET.parse(xml);target=next(n for n in fresh.getroot().findall('nets/net') if n.get('name')=='Net-(U9-SDO/SAO)');target.set('name','Net-(STALE)');fresh.write(xml)
 groups=net_groups(xml);root=ET.parse(xml).getroot();intent={'components':[{'ref':c.get('ref'),'lib_id':c.find('libsource').get('lib')+':'+c.find('libsource').get('part')} for c in root.findall('components/comp')],'nets':[{'name':n,'pins':sorted(p)} for p,n in groups.items() if p]}
 target=[n for n in intent['nets'] if any(s in n['name'] for s in ('Net-(',))]
 if tag in ('encoded-unknown','variable-unknown','bus-unknown'):target=next(( [n] for n in intent['nets'] if 'R5.1' in n['pins']),[])
 for i,n in enumerate(target):n['name']='INTENDED_CLOCK_'+str(i)
 audit=audit_name_origins(out/'probe.kicad_sch',xml,CLI,out/'origin');result=compare_netlist(xml,intent,name_origins=audit['origins']);rec.update({'actual_groups':[{'name':n,'pins':sorted(p)} for p,n in groups.items()],'target':target,'audit':{**audit,'origins':[{'pins':sorted(p),'kind':k} for p,k in audit['origins'].items()]},'result':result,'source_sha':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in files},'xml_sha':hashlib.sha256(xml.read_bytes()).hexdigest()});records.append(rec);print(tag,result['status'],audit['status'],audit['gaps'])
 (O/'native-controls.json').write_text(json.dumps(records,indent=2)+'\n')
