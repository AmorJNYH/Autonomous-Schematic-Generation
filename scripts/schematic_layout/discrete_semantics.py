"""Discrete-part symbol semantics against the exact part.

A two-terminal or three-terminal discrete symbol carries a meaning the netlist
cannot check: a bidirectional TVS drawn for a unidirectional part, an N-channel
MOSFET symbol for a P-channel part, NPN for PNP. Connectivity can match the
intent while the drawing tells the reader the wrong device.

For each intent component this compares what its placed symbol says (cached
library description and pin names) with what the part's own datasheet text or
standard MPN suffix says. A contradiction is FAIL. Ambiguous evidence is
listed as unresolved (INSUFFICIENT); parts with no polarity evidence on either
side are not applicable. This is a semantic cross-check, not a pin map: the
reference contract still owns physical pin numbers.
"""
from pathlib import Path
import re
import shutil
import subprocess

from .sexpr import all_nodes, first, parse

PAGES = 3  # polarity is stated on the first pages: title, features, pinning

# Standard TVS families: "A" (or no letter) is unidirectional, "CA"/"C" bidirectional.
TVS_MPN = re.compile(r'^(?:SMAJ|SMBJ|SMCJ|SMDJ|SMF|SMLJ|P4KE|P4SMA|P6KE|P6SMB|1\.5KE|1\.5SMC|SM6T|SM15T|5KP|15KP|3\.0SMC)'
                     r'[0-9.]+(CA|C|A)?(?:[-/].*)?$', re.I)

FAMILIES = {
    'tvs_direction': {
        'symbol': [('bidirectional', re.compile(r'\bbidirectional\b', re.I)),
                   ('unidirectional', re.compile(r'\bunidirectional\b', re.I))],
        'datasheet': [('bidirectional', re.compile(r'\bbi-?directional\b', re.I)),
                      ('unidirectional', re.compile(r'\buni-?directional\b', re.I))],
    },
    'mos_channel': {
        'symbol': [('N-channel', re.compile(r'\bN-?(?:channel|MOSFET|MOS)\b|\bNMOS\b', re.I)),
                   ('P-channel', re.compile(r'\bP-?(?:channel|MOSFET|MOS)\b|\bPMOS\b', re.I))],
        'datasheet': [('N-channel', re.compile(r'\bN-?channel\b', re.I)),
                      ('P-channel', re.compile(r'\bP-?channel\b', re.I))],
    },
    'bjt_type': {
        'symbol': [('NPN', re.compile(r'\bNPN\b')), ('PNP', re.compile(r'\bPNP\b'))],
        'datasheet': [('NPN', re.compile(r'\bNPN\b')), ('PNP', re.compile(r'\bPNP\b'))],
    },
}
DOMINANCE = 3  # a datasheet that names the complement in passing still decides


def cached_symbols(sheets):
    """lib_id -> (description, pin names) from the schematics' own library caches."""
    found = {}
    for sheet in sheets:
        tree = parse(Path(sheet).read_text(encoding='utf-8'))
        for sym in all_nodes(first(tree, 'lib_symbols', []), 'symbol'):
            desc = ''
            for prop in all_nodes(sym, 'property'):
                if len(prop) > 2 and str(prop[1]) in ('Description', 'ki_description'):
                    desc = str(prop[2])
            pins = set()
            def walk(node):
                for child in node:
                    if isinstance(child, list) and child:
                        if child[0] == 'pin':
                            name = first(child, 'name')
                            if name and len(name) > 1:
                                pins.add(str(name[1]))
                        elif child[0] == 'symbol':
                            walk(child)
            walk(sym)
            found[str(sym[1])] = (desc, pins)
    return found


def symbol_meaning(family, desc, pins):
    hits = {label for label, pattern in FAMILIES[family]['symbol'] if pattern.search(desc)}
    if family == 'tvs_direction' and not hits:
        if pins == {'A1', 'A2'}:
            hits = {'bidirectional'}
        elif {'K', 'A'} <= pins and len(pins) == 2:
            hits = {'unidirectional'}
    return hits.pop() if len(hits) == 1 else None


def datasheet_text(path):
    tool = shutil.which('pdftotext')
    if not tool or not path.is_file():
        return None
    r = subprocess.run([tool, '-l', str(PAGES), '-q', str(path), '-'], capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


def datasheet_meaning(family, text):
    counts = {label: len(pattern.findall(text)) for label, pattern in FAMILIES[family]['datasheet']}
    present = {k: v for k, v in counts.items() if v}
    if not present:
        return None, counts
    if len(present) == 1:
        return next(iter(present)), counts
    (a, na), (b, nb) = sorted(present.items(), key=lambda kv: -kv[1])
    return (a if na >= DOMINANCE * nb else 'ambiguous'), counts


def mpn_meaning(mpn):
    m = TVS_MPN.match(mpn.strip()) if mpn else None
    if not m:
        return None
    return 'bidirectional' if (m.group(1) or '').upper() in ('CA', 'C') else 'unidirectional'


def resolve(path, bases):
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        return p
    for base in bases:
        if (Path(base) / p).is_file():
            return Path(base) / p
    return None


def audit_discrete_semantics(sheets, intent, bases=()):
    cache = cached_symbols(sheets)
    errors, unresolved, checked = [], [], []
    for comp in intent.get('components', []):
        ref, lib_id = comp.get('ref'), str(comp.get('lib_id', ''))
        desc, pins = cache.get(lib_id, ('', set()))
        mpn = str(comp.get('mpn') or comp.get('value') or '')
        text = None
        path = resolve(comp.get('datasheet'), bases)
        for family in FAMILIES:
            drawn = symbol_meaning(family, desc, pins)
            if drawn is None:
                continue
            part, source = None, None
            if family == 'tvs_direction':
                part = mpn_meaning(mpn)
                source = 'MPN suffix' if part else None
            if part is None:
                if text is None and path is not None:
                    text = datasheet_text(path) or ''
                if text:
                    part, counts = datasheet_meaning(family, text)
                    source = 'datasheet first %d pages %s' % (PAGES, counts)
            if part is None:
                continue  # no polarity evidence for this family: not applicable
            row = {'ref': ref, 'family': family, 'lib_id': lib_id, 'symbol': drawn, 'part': part,
                   'mpn': mpn, 'evidence': source}
            if part == 'ambiguous':
                unresolved.append(row)
            elif part != drawn:
                errors.append({**row, 'code': 'symbol_semantics_mismatch',
                               'detail': f'{ref} {mpn}: symbol {lib_id} is {drawn}, part is {part}'})
            else:
                checked.append(row)
    status = 'FAIL' if errors else 'INSUFFICIENT' if unresolved else 'PASS' if checked else 'NOT_APPLICABLE'
    return {'status': status,
            'scope': 'Symbol meaning (TVS direction, MOSFET channel, BJT type) against datasheet text or MPN suffix; '
                     'not physical pin numbers, ratings or footprints.',
            'errors': errors, 'unresolved': unresolved, 'checked': checked}
