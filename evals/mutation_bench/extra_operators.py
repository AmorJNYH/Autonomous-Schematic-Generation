"""Opt-in revision-3 native name-origin probes; legacy TYPES are unchanged."""
import copy
import math
import re
from pathlib import Path
from collections import Counter
from bench_common import get, sha
from schematic_layout.pages import normalize
from schematic_layout.native_hierarchy import NativeHierarchy
from schematic_layout.sexpr import all_nodes, first, parse

EXTRA_TYPES = {'M-NAME-AUTO-LIKE': 'intent_netlist'}
AUTO_LIKE_LITERAL = 'Net-(ASG-PROBE-SDO/SAO)'


def selected_types(requested, revision, legacy):
    selected = list(requested or legacy)
    unknown = sorted(set(selected) - set(legacy) - set(EXTRA_TYPES))
    if unknown:
        raise ValueError('Unknown mutation type(s): ' + ', '.join(unknown))
    if revision != 3 and any(t in EXTRA_TYPES for t in selected):
        raise ValueError('M-NAME-AUTO-LIKE requires --revision 3')
    return selected


def mutate_extra(delivery, kind):
    if kind not in EXTRA_TYPES:
        raise ValueError('Unknown extra mutation type: ' + kind)
    delivery = Path(delivery).resolve()
    plan = {'type': kind, 'expected_gate': EXTRA_TYPES[kind], 'expected_status': 'FAIL',
            'status': 'OUT_OF_SCOPE', 'reason': 'No qualified unique scalar label literal'}
    intent_path = delivery / 'electrical-intent.json'
    if not intent_path.is_file():
        return {**plan, 'reason': 'Intent unavailable'}
    expected = {n['name'] for n in normalize(get(intent_path))['nets']}
    roots = sorted(delivery.glob('*.kicad_sch'))
    root = next((p for p in roots if all_nodes(parse(p.read_bytes().decode()), 'sheet')), roots[0] if roots else None)
    if root is None:
        return {**plan, 'reason': 'Native root unavailable'}
    graph = NativeHierarchy(root, annotations=False)
    if graph.errors or graph.coverage_gaps:
        return {**plan, 'reason': 'Complete portable native hierarchy unavailable'}
    labels = [(path, tree, kind_, node) for path, tree in sorted(graph.trees.items())
              for kind_ in ('label', 'global_label', 'hierarchical_label')
              for node in all_nodes(tree, kind_)]
    if any(all_nodes(t, tag) for t in graph.trees.values() for tag in ('bus', 'bus_entry', 'bus_alias')):
        return {**plan, 'reason': 'Bus naming is unsupported by this scalar operator'}
    counts = Counter(str(n[1]) for _, _, _, n in labels)
    if any(AUTO_LIKE_LITERAL in path.read_bytes().decode() for path in graph.trees):
        return {**plan, 'reason': 'Diagnostic literal already exists in source'}
    interfaces = {str(p[1]) for t in graph.trees.values() for sheet in all_nodes(t, 'sheet')
                  for p in all_nodes(sheet, 'pin')}
    for path, tree, label_kind, node in labels:
        name = str(node[1])
        if (counts[name] != 1 or name not in expected or name == AUTO_LIKE_LITERAL
                or not name or any(c in name for c in '{}$\\"[]:')
                or not all(33 <= ord(c) < 127 for c in name)):
            continue
        if label_kind == 'hierarchical_label' and name in interfaces:
            continue  # A one-object rename may sever a real sheet interface.
        at, uid = all_nodes(node, 'at'), all_nodes(node, 'uuid')
        if len(at) != 1 or len(uid) != 1 or len(uid[0]) != 2 or not str(uid[0][1]):
            continue
        try:
            if len(at[0]) != 4 or not all(math.isfinite(float(v)) for v in at[0][1:]):
                continue
        except (TypeError, ValueError):
            continue
        source = path.read_bytes().decode('utf-8')
        pattern = r'\(\s*' + re.escape(label_kind) + r'\s+"' + re.escape(name) + r'"'
        matches = list(re.finditer(pattern, source))
        if len(matches) != 1:
            continue
        match = matches[0]
        start, end = match.end() - len(name) - 1, match.end() - 1
        altered = source[:start] + AUTO_LIKE_LITERAL + source[end:]
        expected_tree = copy.deepcopy(tree)
        chosen = all_nodes(expected_tree, label_kind)[all_nodes(tree, label_kind).index(node)]
        chosen[1] = AUTO_LIKE_LITERAL
        if parse(altered) != expected_tree:
            continue
        before_sha, intent_sha = sha(path), sha(intent_path)
        path.write_bytes(altered.encode('utf-8'))
        assert sha(intent_path) == intent_sha
        return {**plan, 'status': 'APPLICABLE', 'file': str(path.relative_to(delivery)),
                'objects': [name, AUTO_LIKE_LITERAL], 'before': name, 'after': AUTO_LIKE_LITERAL,
                'label_kind': label_kind, 'label_uuid': str(uid[0][1]),
                'coordinates_mm': [list(map(float, at[0][1:3]))],
                'source_sha_before': before_sha, 'source_sha_after': sha(path),
                'intent_sha256': intent_sha, 'source_name_only': True,
                'operator_scope': 'One unique quoted scalar label literal; all other source bytes and UUID/placement/style are preserved. Rendered text extent can change. Native NAME_ONLY qualification is mandatory; sheet-linked hierarchical interfaces are not renamed.'}
    return plan
