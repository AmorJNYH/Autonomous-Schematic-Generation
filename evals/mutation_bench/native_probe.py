"""Revision-3 probe kinds derive from actual native XML, never label spelling alone."""
import xml.etree.ElementTree as ET
from schematic_layout.pages import normalize


def named_partitions(path):
    root = ET.parse(path).getroot()
    if root.tag != 'export' or root.find('nets') is None or root.find('components') is None:
        raise ValueError('Not a native KiCad XML netlist')
    rows = []
    for net in root.findall('nets/net'):
        pins = tuple(sorted(f"{p.get('ref')}.{p.get('pin')}" for p in net.findall('node')
                            if not p.get('ref', '').startswith('#')))
        if pins:
            rows.append((pins, net.attrib['name']))
    return sorted(rows)


def probe_delta(before, after, before_identity, after_identity, intent):
    old = named_partitions(before)
    new = named_partitions(after)
    partition_changed = sorted(p for p, _ in old) != sorted(p for p, _ in new)
    identity_changed = before_identity != after_identity
    names_changed = old != new and not partition_changed
    expected = {tuple(sorted(n['pins'])): n['name'] for n in normalize(intent)['nets']}
    targets = []
    if names_changed:
        for pins in sorted({p for p, _ in old}):
            before_names = sorted(name for p, name in old if p == pins)
            after_names = sorted(name for p, name in new if p == pins)
            if before_names != after_names:
                targets.append({'pins': list(pins), 'expected': expected.get(pins),
                                'before_names': before_names, 'after_names': after_names})
    kind = ('TOPOLOGY' if partition_changed else 'IDENTITY' if identity_changed else
            'NAME_ONLY' if names_changed else 'NATIVE_NO_OP')
    return {'partitions_changed': partition_changed, 'identity_changed': identity_changed,
            'net_names_changed': names_changed, 'probe_kind': kind, 'name_targets': targets}


def attributable_name_errors(delta, errors):
    """Require a new intent name error on the actual renamed native partition."""
    found = []
    for error in errors:
        entry = error.get('entry', {})
        if entry.get('kind') != 'net_name_mismatch':
            continue
        actual = entry.get('actual', [])
        if not isinstance(actual, list):
            continue
        for target in delta.get('name_targets', []):
            if (target['expected'] is not None and entry.get('expected') == target['expected']
                    and any(name in target['after_names'] and name not in target['before_names'] for name in actual)):
                found.append(error)
                break
    return found
