import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from design_frontier import frontier
class FrontierTests(unittest.TestCase):
    def d(self, deps=None,status='open'):
        return dict(stage='design',status=status,blocked_by=deps or [])
    def e(self, alternatives=None):
        return dict(stage='external',status='open',blocked_by=[],fallback_work=alternatives or [],fallback_evidence=['E1'])
    def test_external_gap_does_not_stop_independent_design(self):
        r=frontier({'FW':self.e(),'BIAS':self.d(),'CONFIG':self.d(['FW'])},{'E1':{}})
        self.assertEqual(r['status'],'CONTINUE_DESIGN');self.assertEqual(r['ready_design_actions'],['BIAS'])
        self.assertEqual(r['blocked_design_actions'],{'CONFIG':['FW']})
    def test_fallback_is_itself_executable(self):
        r=frontier({'DATA':self.e(['ALT']),'ALT':self.d()},{})
        self.assertEqual(r['ready_design_actions'],['ALT']);self.assertFalse(r['errors'])
    def test_closed_dependency_unblocks_action(self):
        r=frontier({'CALC':self.d(status='closed'),'DRAW':self.d(['CALC'])},{})
        self.assertEqual(r['ready_design_actions'],['DRAW'])
    def test_unassessed_fallback_is_not_waiting_success(self):
        e=self.e();e['fallback_evidence']=[]
        self.assertEqual(frontier({'E':e},{})['status'],'INVALID')
    def test_cycles_and_unknown_dependencies_are_invalid(self):
        for work in [{'A':self.d(['B']),'B':self.d(['A'])},{'A':self.d(['MISSING'])}]:
            self.assertEqual(frontier(work,{})['status'],'INVALID')
    def test_handoff_is_not_completed_design_prerequisite(self):
        r=frontier({'MEASURE':dict(stage='validation',status='handoff',blocked_by=[]),'CALC':self.d(['MEASURE'])},{})
        self.assertEqual(r['status'],'WAITING_DEPENDENCIES')
    def test_no_open_actions_does_not_claim_release(self):
        r=frontier({'A':self.d(status='closed')},{})
        self.assertEqual(r['status'],'NO_OPEN_DESIGN_ACTIONS');self.assertNotIn('release',r)
    def test_omitted_dependency_lists_mean_none(self):
        r=frontier({'FW':dict(stage='external',status='open',fallback_evidence=['E1']),'BIAS':dict(stage='design',status='open')},{'E1':{}})
        self.assertFalse(r['errors']);self.assertEqual(r['ready_design_actions'],['BIAS'])
        r=frontier({'A':dict(stage='design',status='open',blocked_by='B')},{})
        self.assertIn('convergence_dependencies',{e['code'] for e in r['errors']})
if __name__=='__main__':unittest.main()
