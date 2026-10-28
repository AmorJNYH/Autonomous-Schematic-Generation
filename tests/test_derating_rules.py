"""The derating spec (I/II/III levels from T/CPSS 1013, GJB/Z 35 and T/CPSS 1006) is one file shared with
schematic-review: every rule names a known kind, a measure, a condition and a cited page, the levels run from most to
least derating, and both repositories hold the same bytes (user 2026-10-27)."""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from schematic_layout import part_classes as pc

JSON_PATH = ROOT / 'references' / 'derating-rules.json'
MD_PATH = ROOT / 'references' / 'derating-rules.md'
SR = Path.home() / '.agents' / 'skills' / 'schematic-review' / 'references'
LIBRARY = Path.home() / 'Documents' / '知识库' / 'HardwareWiki'
SPEC = json.loads(JSON_PATH.read_text(encoding='utf-8'))
LEVELS = ('I', 'II', 'III')
# Direction of each measure from level I to level III: less derating allows a larger ratio or temperature and asks a
# smaller margin or life.
RISING = {'ratio', 'pulse_ratio', 'tj_percent', 'max_c', 'max_rise_k', 'max_v'}
FALLING = {'margin_c', 'min_hours', 'min_years'}


class DeratingSpecTests(unittest.TestCase):
    def test_header(self):
        self.assertEqual(SPEC['levels'], list(LEVELS))
        self.assertEqual(sorted(SPEC['priority']), sorted(SPEC['sources']))
        self.assertEqual(SPEC['priority'][0], 'cpss1013')

    def test_every_rule_is_well_formed(self):
        kinds = set(pc.KINDS) | set(SPEC['extra_kinds'])
        for rule in SPEC['rules']:
            rid = rule['id']
            self.assertTrue(set(rule['kinds']) <= kinds, rid)
            self.assertIn(rule['measure'], SPEC['measures'], rid)
            self.assertIn(rule['condition'], SPEC['conditions'], rid)
            source = SPEC['sources'][rule['source']]
            self.assertTrue(1 <= rule['page'] <= source['pages'], rid)
            self.assertEqual(tuple(rule['values']), LEVELS, rid)
            numeric = all(isinstance(v, (int, float)) for v in rule['values'].values())
            self.assertEqual(numeric, rule['measure'] != 'text', rid)

    def test_ids_are_unique_and_one_rule_per_type_parameter_condition(self):
        ids = [r['id'] for r in SPEC['rules']]
        self.assertEqual(len(ids), len(set(ids)))
        keys = [(r['type'], r['parameter'], r['condition']) for r in SPEC['rules']]
        self.assertEqual(sorted(k for k in set(keys) if keys.count(k) > 1), [])

    def test_an_ungraded_source_gives_one_value_for_all_levels(self):
        for rule in SPEC['rules']:
            if not SPEC['sources'][rule['source']]['graded']:
                self.assertEqual(len(set(map(str, rule['values'].values()))), 1, rule['id'])

    def test_levels_run_from_most_to_least_derating(self):
        for rule in SPEC['rules']:
            v = [rule['values'][k] for k in LEVELS]
            if rule['measure'] in RISING:
                self.assertEqual(v, sorted(v), rule['id'])
            elif rule['measure'] in FALLING:
                self.assertEqual(v, sorted(v, reverse=True), rule['id'])

    def test_the_document_lists_every_rule(self):
        listed = re.findall(r'^\| ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+) \|', MD_PATH.read_text(encoding='utf-8'), flags=re.M)
        self.assertEqual(sorted(listed), sorted(r['id'] for r in SPEC['rules']))

    @unittest.skipUnless((LIBRARY / 'raw' / 'Standard').is_dir(), 'HardwareWiki not installed')
    def test_sources_are_the_library_files(self):
        for key, source in SPEC['sources'].items():
            path = LIBRARY / source['path']
            self.assertTrue(path.is_file(), source['path'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source['sha256'], key)

    @unittest.skipUnless((SR / 'derating-rules.json').is_file(), 'schematic-review not installed')
    def test_schematic_review_holds_the_same_files(self):
        for name in ('derating-rules.json', 'derating-rules.md', 'stress-spec.md'):
            self.assertEqual((SR / name).read_bytes(), (ROOT / 'references' / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()
