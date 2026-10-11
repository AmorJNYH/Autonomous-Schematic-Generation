"""Explain existing rail rejection predicates without changing their outcomes."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'scripts'), str(HERE / 'fixtures/drawing')]
from recipe_board import draw
from schematic_layout.geometry import Box, TextField
from schematic_layout.recipes import Sheet, _rail_collision_diagnostic
from schematic_layout.routing import segment_hits_box
from schematic_layout.scene import read_scene


class RailDiagnosticPredicatesTests(unittest.TestCase):
    def diagnostic(self, box, segments=(), obstacles=(), sources=(), page=Box(0, 0, 100, 100)):
        return _rail_collision_diagnostic(box, 'SUPPLY', 'power:+5V', (20, 20), 2, 'Value',
                                          segments, obstacles, sources, page)

    def test_all_reasons_and_exact_positions_are_retained(self):
        box = Box(-1, 10, 2, 12)
        segment = ('OTHER', (-2, 11), (3, 11))
        obstacle = Box(0, 9, 3, 13)
        result = self.diagnostic(box, [segment], [obstacle], [{'kind': 'physical_pin', 'pin_id': 'U42.3'}])
        self.assertEqual('Value', result['field'])
        self.assertEqual([-1, 10, 2, 12], result['box'])
        self.assertEqual(['foreign_wire', 'obstacle_overlap', 'outside_page'],
                         [row['kind'] for row in result['reasons']])
        self.assertEqual({'kind': 'foreign_wire', 'segment_index': 0, 'net': 'OTHER',
                          'endpoints': [(-2, 11), (3, 11)]}, result['reasons'][0])
        self.assertEqual({'kind': 'physical_pin', 'pin_id': 'U42.3'}, result['reasons'][1]['object'])
        self.assertEqual([0, 9, 3, 13], result['reasons'][1]['box'])
        self.assertEqual(['left'], result['reasons'][2]['edges'])

    def test_same_net_and_exact_box_page_contact_keep_existing_predicates(self):
        box = Box(0, 10, 2, 12)
        segment = ('SUPPLY', (-2, 11), (3, 11))
        touching = Box(2, 10, 4, 12)
        self.assertEqual([], self.diagnostic(box, [segment], [touching])['reasons'])
        self.assertTrue(box.inside(Box(0, 0, 100, 100)))
        self.assertFalse(box.overlaps(touching))

    def test_each_page_edge_uses_original_inside_rule(self):
        for edge, box in (('left', Box(-1, 10, 2, 12)), ('right', Box(99, 10, 101, 12)),
                          ('top', Box(10, -1, 12, 2)), ('bottom', Box(10, 99, 12, 101))):
            with self.subTest(edge=edge):
                self.assertEqual([edge], self.diagnostic(box)['reasons'][0]['edges'])

    def test_equal_obstacle_boxes_keep_distinct_objects_and_input_identity(self):
        box = Box(10, 10, 12, 12)
        obstacles = [Box(9, 9, 13, 13), Box(9, 9, 13, 13)]
        identities = list(map(id, obstacles))
        sources = [{'kind': 'component_body', 'reference': 'R1'},
                   {'kind': 'component_body', 'reference': 'R2'}]
        result = self.diagnostic(box, obstacles=obstacles, sources=sources)
        self.assertEqual(['R1', 'R2'], [row['object']['reference'] for row in result['reasons']])
        self.assertEqual(identities, list(map(id, obstacles)))

    def test_missing_provenance_does_not_invent_owner(self):
        result = self.diagnostic(Box(10, 10, 12, 12), obstacles=[Box(9, 9, 13, 13)])
        self.assertEqual({'kind': 'unknown', 'index': 0}, result['reasons'][0]['object'])

    def test_diagnostic_reasons_agree_with_old_boolean_guard(self):
        page = Box(0, 0, 100, 100)
        obstacles = [Box(10, 10, 15, 15)]
        segments = [('OTHER', (0, 20), (100, 20)), ('SUPPLY', (0, 30), (100, 30))]
        for box in (Box(9, 9, 11, 11), Box(19, 19, 21, 21), Box(19, 29, 21, 31),
                    Box(50, 50, 51, 51), Box(0, 0, 1, 1), Box(99, 99, 101, 101)):
            with self.subTest(box=box):
                original = (any(segment_hits_box(a, b, box) for net, a, b in segments if net != 'SUPPLY')
                            or any(box.overlaps(o) for o in obstacles) or not box.inside(page))
                self.assertEqual(bool(original), bool(self.diagnostic(box, segments, obstacles)['reasons']))


class RailDiagnosticBuildTests(unittest.TestCase):
    def reject(self, sheet):
        with self.assertRaises(ValueError) as caught:
            sheet.build('rail-diagnostic-synthetic')
        self.assertIs(type(caught.exception), ValueError)
        message = str(caught.exception)
        prefix, encoded = message.split('; diagnostic=', 1)
        self.assertIn('collides; change the recipe direction or length', prefix)
        return prefix, json.loads(encoded)

    @staticmethod
    def envelopes(sheet, index=0):
        net, symbol, end = sheet.powers[index]
        _, body, down = sheet._power_shape(symbol)
        box = Box(body.x_min + end[0], body.y_min + end[1], body.x_max + end[0], body.y_max + end[1])
        value_at = (end[0], box.y_max + 0.9 if down else box.y_min - 0.9)
        return box, TextField(net, *value_at, 0, 1.0).box()

    def test_body_and_value_annotation_failure_have_precise_field_and_no_text_dump(self):
        for field, index in (('body', 0), ('Value', 1)):
            with self.subTest(field=field):
                sheet = draw()
                box = self.envelopes(sheet)[index]
                sheet.text('PRIVATE_ANNOTATION_TEXT', box.center, font=0.254)
                prefix, diagnostic = self.reject(sheet)
                self.assertEqual(field, diagnostic['field'])
                self.assertEqual(0, diagnostic['request_index'])
                annotations = [row for row in diagnostic['reasons']
                               if row['kind'] == 'obstacle_overlap' and row['object']['kind'] == 'annotation_text']
                self.assertTrue(annotations, diagnostic)
                self.assertEqual('text', annotations[0]['object']['field'])
                for expected, actual in zip(box.center, annotations[0]['object']['anchor']):
                    self.assertAlmostEqual(expected, actual)
                self.assertNotIn('PRIVATE_ANNOTATION_TEXT', json.dumps(diagnostic))

    def test_prior_rail_body_and_value_are_distinct_obstacles(self):
        for field, index in (('body', 0), ('Value', 1)):
            with self.subTest(field=field):
                sheet = draw()
                first = sheet.powers[0]
                target = self.envelopes(sheet)[index]
                _, local_body, _ = sheet._power_shape(first[1])
                end = (target.center[0] - local_body.center[0], target.center[1] - local_body.center[1])
                sheet.powers.insert(1, (first[0], first[1], end))
                _, diagnostic = self.reject(sheet)
                self.assertEqual(1, diagnostic['request_index'])
                earlier = [row['object'] for row in diagnostic['reasons']
                           if row['kind'] == 'obstacle_overlap' and row['object']['kind'] == 'earlier_rail']
                self.assertTrue(any(row['request_index'] == 0 and row['field'] == field for row in earlier), diagnostic)

    def test_component_pin_reserved_foreign_and_page_sources_are_identified(self):
        # The base is only the public synthetic recipe fixture, never round CAD.
        base = draw()
        root, _ = base.build('rail-diagnostic-synthetic-base')
        scene = read_scene(root)
        component = next(s for s in scene.symbols if s.ref == 'U1')
        pin = next(p for p in component.pins if p.id == 'U1.4')
        segments, _ = base._segments()
        foreign = next((net, a, b) for net, a, b in segments
                       if net != base.powers[0][0] and a[1] == b[1])
        mid = tuple((a + b) / 2 for a, b in zip(foreign[1], foreign[2]))
        cases = [('component_body', component.body.center), ('physical_pin', pin.inner),
                 ('reserved_region', (scene.page.x_max - 60, scene.page.y_max - 30)),
                 ('foreign_wire', mid), ('outside_page', (0, 0))]
        for kind, center in cases:
            with self.subTest(kind=kind):
                sheet = draw()
                net, symbol, _ = sheet.powers[0]
                _, body, _ = sheet._power_shape(symbol)
                # Keep every legitimate piece marked; adding a synthetic request
                # must reach the rail guard rather than the earlier connectivity guard.
                sheet.powers.append((net, symbol, (center[0] - body.center[0], center[1] - body.center[1])))
                _, diagnostic = self.reject(sheet)
                if kind == 'component_body':
                    self.assertTrue(any(row.get('object', {}).get('reference') == 'U1' for row in diagnostic['reasons']))
                elif kind == 'physical_pin':
                    self.assertTrue(any(row.get('object', {}).get('pin_id') == 'U1.4' for row in diagnostic['reasons']))
                elif kind == 'reserved_region':
                    self.assertTrue(any(row.get('object', {}).get('kind') == kind for row in diagnostic['reasons']))
                else:
                    self.assertIn(kind, [row['kind'] for row in diagnostic['reasons']])


if __name__ == '__main__':
    unittest.main()
