"""Native marker applicability plus explicit XML evidence-integrity negatives.

XML edits are transport/metadata controls, not native CAD faults. Native controls
use self-contained cached symbols and real KiCad; no installed library borrowing.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.external_supply import audit_external_supply, judge
from schematic_layout.native import find_cli
from schematic_layout.sexpr import parse, dump, first, all_nodes, value
from test_filtered_supply import INTENT, PARTS, nets, xml

TMP = Path('/tmp/codex-work/filtered-supply-native-tests')
CLI = find_cli()

class EvidenceIntegrityTests(unittest.TestCase):
    def evaluate(self, change, custom=False):
        intent = copy.deepcopy(INTENT)
        parts = dict(PARTS)
        if custom:
            intent['components'][1].update(lib_id='Audit:Series', fields={'ComponentRole': 'series_resistor'})
            parts['R1'] = ('Audit', 'Series', '10')
        tree = ET.fromstring(xml(nets(), parts=parts))
        if custom:
            comp = tree.find("components/comp[@ref='R1']")
            fields = ET.SubElement(comp, 'fields')
            ET.SubElement(fields, 'field', {'name': 'ComponentRole'}).text = 'series_resistor'
            ET.SubElement(comp, 'property', {'name': 'ComponentRole', 'value': 'series_resistor'})
        change(tree)
        TMP.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            p = Path(tmp)/'input.xml'; ET.ElementTree(tree).write(p)
            return judge(p, intent, {'FLGX1': '#FLG1'})
    def rejected(self, result):
        self.assertIn(result['status'], ('FAIL', 'INSUFFICIENT'), result)
    def test_exact_actual_via_types_not_library_types(self):
        for typ in ('power_in', 'passive+power_in', 'passive+passive'):
            with self.subTest(pintype=typ):
                self.rejected(self.evaluate(lambda r: r.find("nets/net/node[@ref='R1'][@pin='1']").set('pintype', typ)))
    def test_missing_actual_via_type_is_unknown(self):
        self.assertEqual(self.evaluate(lambda r: r.find("nets/net/node[@ref='R1'][@pin='1']").attrib.pop('pintype'))['status'], 'INSUFFICIENT')
    def test_actual_via_pin_coverage_is_unique_and_complete(self):
        def duplicate(r):
            net = next(n for n in r.findall('nets/net') if n.find("node[@ref='R1'][@pin='1']") is not None)
            net.append(copy.deepcopy(net.find("node[@ref='R1'][@pin='1']")))
        def missing(r):
            net = next(n for n in r.findall('nets/net') if n.find("node[@ref='R1'][@pin='1']") is not None)
            net.remove(net.find("node[@ref='R1'][@pin='1']"))
        for edit in (duplicate, missing): self.rejected(self.evaluate(edit))
    def test_static_pin_numbers_cannot_be_missing_or_duplicate(self):
        for num in (None, '1'):
            def edit(r):
                p = r.findall("libparts/libpart[@lib='Device'][@part='R']/pins/pin")[1]
                if num is None: p.attrib.pop('num')
                else: p.set('num', num)
            with self.subTest(number=num): self.rejected(self.evaluate(edit))
    def test_explicit_role_conflict_and_ambiguous_duplicates(self):
        for role in ('LED', 'series_resistor'):
            def edit(r): ET.SubElement(r.find("components/comp[@ref='R1']/fields"), 'field', {'name': 'ComponentRole'}).text = role
            with self.subTest(duplicate_role=role): self.rejected(self.evaluate(edit, custom=True))
        self.rejected(self.evaluate(lambda r: setattr(r.find("components/comp[@ref='R1']/fields/field"), 'text', 'LED'), custom=True))
    def test_role_property_cannot_conflict_with_field(self):
        self.rejected(self.evaluate(lambda r: r.find("components/comp[@ref='R1']/property[@name='ComponentRole']").set('value', 'LED'), custom=True))
    def test_matching_role_two_native_representations_passes(self):
        self.assertEqual(self.evaluate(lambda r: None, custom=True)['status'], 'PASS')
    def test_alias_node_must_be_actual_power_output(self):
        for typ in ('power_in', 'passive', 'power_out+power_in'):
            with self.subTest(pintype=typ): self.rejected(self.evaluate(lambda r: r.find("nets/net/node[@ref='FLGX1']").set('pintype', typ)))
        self.assertEqual(self.evaluate(lambda r: r.find("nets/net/node[@ref='FLGX1']").attrib.pop('pintype'))['status'], 'INSUFFICIENT')
    def test_alias_pin_number_is_not_invented(self):
        self.assertEqual(self.evaluate(lambda r: r.find("nets/net/node[@ref='FLGX1']").attrib.pop('pin'))['status'], 'INSUFFICIENT')

# Self-created CAD, with numeric unit/style syntax. UUIDs and positions are
# fixed; only the declared cached definition or explicit role varies.
FX='(effects (font (size 1 1)))'
def pin(number, name, typ, x=0, angle=0):
    return f'(pin {typ} line (at {x} 0 {angle}) (length 2.54) (name {json.dumps(name)} {FX}) (number "{number}" {FX}))'
def library(lid, definitions, power=False, extra=''):
    return f'(symbol "{lid}" '+('(power) ' if power else '')+'(in_bom yes) (on_board yes) '+definitions+extra+')'
def placed(ref,lid,x,unit=1,style=1,role=None):
    roleprop=f'(property "ComponentRole" "{role}" (at {x} 55 0) {FX})' if role else ''
    return f'(symbol (lib_id "{lid}") (at {x} 50 0) (unit {unit}) (convert {style}) (in_bom yes) (on_board yes) (dnp no) (uuid "{x:08d}-0000-4000-8000-000000000001") (property "Reference" "{ref}" (at {x} 54 0) {FX}) (property "Value" "10" (at {x} 46 0) {FX}) {roleprop}(instances (project "probe" (path "/00000000-0000-4000-8000-000000000001" (reference "{ref}") (unit {unit})))))'
def cad(case):
    unit, style, role, irole = 1,1,None,None
    marker = '(symbol "Marker_1_1" '+pin(1,'OUT','power_out')+')'
    if case=='unit2': marker='(symbol "Marker_1_1" '+pin(1,'IN','power_in')+')(symbol "Marker_2_1" '+pin(2,'OUT','power_out')+')';unit=2
    elif case=='common0':marker=marker.replace('Marker_1_1','Marker_0_1')+'(symbol "Marker_1_1")'
    elif case=='style0':marker=marker.replace('Marker_1_1','Marker_1_0')
    elif case in ('active_style2','inactive_style2'):
        marker='(symbol "Marker_1_1" '+pin(1,'IN','power_in')+')(symbol "Marker_1_2" '+pin(1,'OUT','power_out')+')';style=2 if case=='active_style2' else 1
    elif case=='unknown':marker=marker.replace('Marker_1_1','Marker_UNKNOWN')
    flag=library('Audit:Marker',marker,True)
    if case=='missing':flag='(symbol "Audit:Marker" (extends "Audit:Absent"))'
    elif case=='cycle':flag='(symbol "Audit:Marker" (extends "Audit:Other"))(symbol "Audit:Other" (extends "Audit:Marker"))'
    viaid='Device:R';vp='(symbol "R_1_1" '+pin(1,'A','passive',-5.08)+pin(2,'B','passive',5.08,180)+')';vstyle=1
    if case=='via_style2':vp+='(symbol "R_1_2" '+pin(1,'A','power_in',-5.08)+pin(2,'B','passive',5.08,180)+')';vstyle=2
    if case=='via_inactive_third':vp+='(symbol "R_2_1" '+pin(3,'OTHER','power_out')+')'
    if case.startswith('role_'):
        viaid='Audit:Series';vp=vp.replace('R_1_1','Series_1_1');irole='series_resistor';role={'role_match':'series_resistor','role_LED':'LED','role_lamp':'lamp','role_photo':'photoresistor','role_missing':None}[case]
    if case.startswith('device_role_'):
        role={'device_role_LED':'LED','device_role_lamp':'lamp','device_role_photo':'photoresistor','device_role_match':'series_resistor','device_role_missing':None}[case]
    libs=library('Audit:Source','(symbol "Source_1_1" '+pin(1,'OUTPUT','power_out',5.08,180)+')')+library('Audit:Load','(symbol "Load_1_1" '+pin(1,'VDD','power_in',-5.08)+')')+library(viaid,vp)+flag
    wires=''.join(f'(wire (pts (xy {a} 50) (xy {b} 50)) (stroke (width 0) (type default)) (uuid "{i:08d}-1111-4111-8111-000000000001"))' for i,(a,b) in enumerate(((35.08,40),(40,44.92),(55.08,60),(60,64.92)),1))
    labels=''.join(f'(label "{n}" (at {x} 50 0) {FX} (uuid "{i:08d}-2222-4222-8222-000000000001"))' for i,(n,x) in enumerate((('PVCC',40),('AVCC',60)),1))
    tree=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid "00000000-0000-4000-8000-000000000001") (paper "A4") (lib_symbols {libs}) {placed("U9","Audit:Source",30)} {placed("R1",viaid,50,style=vstyle,role=role)} {placed("U1","Audit:Load",70)} {placed("#FLG1","Audit:Marker",60,unit,style)} {wires}{labels}(sheet_instances (path "/" (page "1"))))'
    intent={'components':[{'ref':'U9','lib_id':'Audit:Source','value':'10'},{'ref':'R1','lib_id':viaid,'value':'10','fields':{'ComponentRole':irole} if irole else {}},{'ref':'U1','lib_id':'Audit:Load','value':'10'}],'nets':[{'name':'PVCC','pins':['U9.1','R1.1']},{'name':'AVCC','pins':['R1.2','U1.1']}],'filtered_supply':[{'net':'AVCC','from':'PVCC','via':'R1','reason':'self-created native qualification'}]}
    return tree,intent

@unittest.skipUnless(CLI, 'KiCad CLI required for real-native controls')
class NativeQualificationTests(unittest.TestCase):
    def evaluate(self,case):
        TMP.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            p=Path(tmp);text,intent=cad(case);root=p/'probe.kicad_sch';root.write_text(text)
            env={'TMPDIR':str(p),'KICAD_CONFIG_HOME':str(p/'config'),'XDG_CACHE_HOME':str(p/'cache')}
            for key in ('KICAD_CONFIG_HOME','XDG_CACHE_HOME'):Path(env[key]).mkdir()
            with patch.dict(os.environ,env):
                r=subprocess.run([CLI,'sch','export','netlist','--format','kicadxml','-o',str(p/'native.xml'),str(root)],capture_output=True,text=True,timeout=30)
                if case not in ('unknown','missing','cycle'):self.assertEqual(r.returncode,0,r.stderr)
                result=audit_external_supply(root,[root],intent,p/'native.xml',CLI,p/'marker-probe')
            self.assertEqual(root.read_text(),text)
            native=p/'marker-probe/external-supply-netlist.xml';nodes=[]
            if native.exists():nodes=[n.attrib for n in ET.parse(native).getroot().findall('nets/net/node') if n.get('ref')=='FLGX1']
            return result,nodes
    def test_actual_unit_common_unit_and_style_output_positives(self):
        for case in ('unit2','common0','style0','active_style2'):
            with self.subTest(case=case):
                result,nodes=self.evaluate(case);self.assertEqual(result['status'],'PASS',result);self.assertEqual(nodes[0]['pintype'],'power_out')
    def test_inactive_style_output_cannot_qualify_input(self):
        result,_=self.evaluate('inactive_style2');self.assertIn(result['status'],('FAIL','INSUFFICIENT'),result)
    def test_unknown_or_unresolved_cached_definition_stays_insufficient(self):
        for case in ('missing','cycle','unknown'):
            with self.subTest(case=case):self.assertEqual(self.evaluate(case)[0]['status'],'INSUFFICIENT')
    def test_native_via_type_and_whole_library_third_pin(self):
        for case in ('via_style2','via_inactive_third'):
            with self.subTest(case=case):self.assertEqual(self.evaluate(case)[0]['status'],'FAIL')
    def test_explicit_native_role_conflicts_but_legacy_missing_role_is_compatible(self):
        for case in ('role_LED','role_lamp','role_photo','role_match','role_missing'):
            with self.subTest(case=case):
                self.assertEqual(self.evaluate(case)[0]['status'],'PASS' if case in ('role_match','role_missing') else 'FAIL')
    def test_explicit_nonseries_native_role_rejected_when_intent_role_absent(self):
        for case in ('device_role_LED','device_role_lamp','device_role_photo','device_role_match','device_role_missing'):
            with self.subTest(case=case):
                text,intent=cad(case)
                self.assertNotIn('ComponentRole',intent['components'][1]['fields'])
                self.assertEqual(self.evaluate(case)[0]['status'],'PASS' if case in ('device_role_match','device_role_missing') else 'FAIL')
    def test_ambiguous_placed_selector_is_not_resolved_by_first_value(self):
        # Source evidence ambiguity, not an additional qualified native CAD fault.
        from schematic_layout.external_supply import _scan
        TMP.mkdir(parents=True, exist_ok=True)
        for extra in ('(unit 2)', '(body_style 2)'):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory(dir=TMP) as tmp:
                text,_=cad('unit2');tree=parse(text)
                sym=next(s for s in all_nodes(tree,'symbol') if value(s,'lib_id')=='Audit:Marker')
                sym.append(parse(extra));p=Path(tmp)/'input.kicad_sch';p.write_text(dump(tree))
                self.assertTrue(_scan([p])[2])
if __name__=='__main__':unittest.main()
