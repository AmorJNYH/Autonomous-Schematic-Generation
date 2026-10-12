"""Qualify automatic-looking names with same-source native counterfactuals.

XML has no name-origin flag. This deliberately narrow scalar-label audit leaves
bus aliases, text variables, encoded labels and power-name collisions unknown.
"""
import copy
import hashlib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from .native_hierarchy import NativeHierarchy, SUPPORTED_VERSIONS
from .sexpr import all_nodes, dump, first, value


def net_groups(path):
    root = ET.parse(path).getroot()
    return {frozenset(n.get('ref') + '.' + n.get('pin') for n in net.findall('node')
                      if not n.get('ref', '').startswith('#')): net.get('name')
            for net in root.findall('nets/net') if net.findall('node')}


def identities(path):
    components = ET.parse(path).getroot().findall('components/comp')
    for c in components:
        for prop in c.findall("property[@name='Sheetfile']"):
            c.remove(prop)  # Native copy location; UUID sheetpath remains bound.
    return {c.get('ref'): ET.tostring(c, encoding='unicode') for c in components}


def _walk(node):
    if isinstance(node, list) and node:
        yield node
        for child in node:
            yield from _walk(child)


def _audit_name_origins(schematic, xml, cli, output):
    """Return pin-bound EXPLICIT/AUTOMATIC evidence, never infer from regex.

    Fresh source export must match the supplied XML in names, partitions and
    complete component XML. All named interfaces are renamed consistently in a
    private hierarchy; repeated page instances are processed by native KiCad.
    """
    schematic = Path(schematic).resolve()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    result = {'status': 'INSUFFICIENT', 'origins': {}, 'gaps': [], 'commands': [],
              'source_sha256': {}, 'xml_sha256': hashlib.sha256(Path(xml).read_bytes()).hexdigest()}
    graph = NativeHierarchy(schematic, annotations=False)
    result['source_sha256'] = graph.file_sha256
    if graph.errors or graph.coverage_gaps:
        result['gaps'].append('Incomplete native hierarchy')
        return result
    trees = copy.deepcopy(graph.trees)
    names = set()
    power_names = set()
    power_nodes = []
    for tree in trees.values():
        if str(value(tree, "version", "")) not in SUPPORTED_VERSIONS:
            result["gaps"].append("Unsupported native naming version")
        if all_nodes(tree, 'bus') or all_nodes(tree, 'bus_entry') or all_nodes(tree, 'bus_alias'):
            result['gaps'].append('Bus naming is not qualified')
        for node in _walk(tree):
            if node[0] in ('label', 'global_label', 'hierarchical_label') or (
                    node[0] == 'pin' and len(node) > 1 and isinstance(node[1], str)
                    and first(node, 'at') is not None and first(node, 'uuid') is not None):
                name = str(node[1])
                if not name or any(c in name for c in '{}$\\') or not all(32 <= ord(c) < 127 for c in name):
                    result['gaps'].append('Encoded, variable or non-ASCII interface name is not qualified')
                names.add(name)
            if node[0] == 'pin' and len(node) > 1 and node[1] in ('power_in', 'power_out'):
                power_names.add(str(value(node, 'name', '')))
                if 'hide' in node or value(node, 'hide') == 'yes':
                    power_nodes.append(first(node, 'name'))
            if node[0] == 'extends':
                result['gaps'].append('Inherited symbol naming is not qualified')
        cache = first(tree, 'lib_symbols', [])
        power_ids = {str(s[1]) for s in all_nodes(cache, 'symbol') if first(s, 'power') is not None}
        cache_ids = {str(s[1]) for s in all_nodes(cache, 'symbol')}
        for symbol in all_nodes(tree, 'symbol'):
            if str(value(symbol, 'lib_id', '')) not in cache_ids:
                result['gaps'].append('Missing embedded symbol naming inventory')
            if str(value(symbol, 'lib_id', '')) in power_ids:
                for prop in all_nodes(symbol, 'property'):
                    if prop[1] == 'Value':
                        power_names.add(str(prop[2]))
                        power_nodes.append(prop)
    if any(any(c in n for c in '{}$\\') for n in power_names):
        result['gaps'].append('Variable or encoded power-pin naming is not qualified')
    if result['gaps']:
        result['gaps'] = sorted(set(result['gaps']))
        return result
    prefix = 'ASG_ORIGIN_' + hashlib.sha256(Path(xml).read_bytes()).hexdigest()[:16] + '_'
    # Do not let a source name collide with a diagnostic marker.
    if any(prefix in str(atom) for tree in trees.values() for node in _walk(tree)
           for atom in node if not isinstance(atom, list)):
        result['gaps'].append('Diagnostic marker collision')
        return result
    names.update(str(n[2] if n[0] == 'property' else n[1]) for n in power_nodes if n)
    mapping = {n: prefix + str(i) for i, n in enumerate(sorted(names))}
    for node in power_nodes:
        index = 2 if node[0] == 'property' else 1
        node[index] = mapping[str(node[index])]
    source_dir = output / 'source'
    tagged_dir = output / 'tagged'
    for path, tree in trees.items():
        relative = path.relative_to(graph.base)
        for folder in (source_dir, tagged_dir):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != graph.file_sha256[relative.as_posix()]:
                result['gaps'].append('Source changed during provenance audit')
                return result
            target.write_bytes(data)
        for node in _walk(tree):
            if node[0] in ('label', 'global_label', 'hierarchical_label') or (
                    node[0] == 'pin' and len(node) > 1 and first(node, 'at') is not None and first(node, 'uuid') is not None):
                node[1] = mapping[str(node[1])]
        (tagged_dir / relative).write_text(dump(tree) + '\n')
    relative = schematic.relative_to(graph.base)
    for folder in (source_dir, tagged_dir):
        project = schematic.with_suffix('.kicad_pro')
        if project.is_file():
            (folder / relative.with_suffix('.kicad_pro')).write_bytes(project.read_bytes())
        argv = [str(cli), 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o',
                str(folder / 'origin.xml'), str(folder / relative)]
        run = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        result['commands'].append({'argv': argv, 'returncode': run.returncode,
                                   'stdout': run.stdout, 'stderr': run.stderr})
        if run.returncode != 0 or not (folder / 'origin.xml').is_file():
            result['gaps'].append('Origin native export unavailable')
            return result
    actual = net_groups(xml)
    fresh = net_groups(source_dir / 'origin.xml')
    tagged = net_groups(tagged_dir / 'origin.xml')
    if actual != fresh or identities(xml) != identities(source_dir / 'origin.xml'):
        result['gaps'].append('Supplied XML does not match fresh same-source native export')
        return result
    if set(actual) != set(tagged) or identities(xml) != identities(tagged_dir / 'origin.xml'):
        result['gaps'].append('Diagnostic naming changed partitions or component identity')
        return result
    for pins, name in actual.items():
        # A scalar explicit name is proved by a tagged native name on the same
        # physical partition. Power/hidden-power conflicts remain unknown.
        if prefix in tagged[pins]:
            result['origins'][pins] = 'EXPLICIT'
        elif name == tagged[pins] and not any(name == p or name.endswith('/' + p)
                                             for p in power_names if p):
            result['origins'][pins] = 'AUTOMATIC'
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != graph.file_sha256[path.relative_to(graph.base).as_posix()]
           for path in graph.trees):
        result['origins'] = {}
        result['gaps'].append('Source changed during provenance audit')
        return result
    result['status'] = 'MEASURED'
    return result


def audit_name_origins(schematic, xml, cli, output):
    """Unavailable or invalid provenance is coverage loss, never permission."""
    try:
        return _audit_name_origins(schematic, xml, cli, output)
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        return {"status": "INSUFFICIENT", "origins": {}, "gaps": [
            "Origin evidence unavailable: " + type(exc).__name__],
            "commands": [], "source_sha256": {}, "xml_sha256": None}
