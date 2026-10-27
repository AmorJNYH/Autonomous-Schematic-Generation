"""Which parts the design netlist must name exactly (references/part-roles.md section 1).

A part's class follows from its reference prefix and symbol family, never from a designer's choice:
core parts (ICs, transistors, transformers, modules) and exact-MPN parts need an MPN and a datasheet;
a custom magnetic names its design sheet in ``fields.DesignSheet`` instead. Spec parts are a whitelist
(resistors, non-polarized capacitors, test points, jumpers, switches, mechanical items) fixed by value
and specification; any part not recognized as core or spec is an exact-MPN part. A datasheet cited for a part in a calculation or a data
gap must be the datasheet the design netlist gives that part.
"""

import hashlib
import os
import re
from pathlib import Path

from .citations import library_present, locate, parse
from .discrete_semantics import resolve

CORE, EXACT, SPEC = 'core', 'exact', 'spec'
CLASS_NAMES = {CORE: '核心器件', EXACT: '料号件'}


CORE_PREFIXES = ('U', 'Q', 'T', 'A', 'MODULE', 'REF')
CORE_SYMBOLS = ('Q_', 'Transformer')
SPEC_PREFIXES = ('TP', 'JP', 'H', 'MB', 'FID', 'HS', 'LOGO', 'SW', 'MX')
SPEC_SYMBOLS = ('TestPoint', 'MountingHole', 'Fiducial', 'SolderJumper', 'Jumper', 'Heatsink', 'SW_', 'KEYSW', 'MX-')


def part_class(comp):
    """core / exact / spec for one design-netlist component."""
    ref = str(comp.get('ref', ''))
    prefix = re.match(r'[A-Z]*', ref.upper()).group()
    lib = str(comp.get('lib_id', ''))
    library, _, name = lib.rpartition(':')
    if name == 'TestPoint':
        return SPEC
    if prefix in CORE_PREFIXES or name.startswith(CORE_SYMBOLS) or library.startswith('Transistor'):
        return CORE
    if prefix in SPEC_PREFIXES or name.startswith(SPEC_SYMBOLS):
        return SPEC
    if prefix in ('R', 'RV') and not name.startswith(('Thermistor', 'Varistor')):
        return SPEC
    if prefix == 'C' and not name.startswith(('C_Polarized', 'CP')):
        return SPEC
    return EXACT


def text(value):
    return isinstance(value, str) and bool(value.strip())


def find(path, bases):
    """A datasheet path from the design netlist or a citation: absolute, under the delivery, or in the library."""
    if not text(path):
        return None
    found = resolve(os.path.expanduser(path), bases)
    if found and Path(found).is_file():
        return Path(found)
    return locate(path, bases)


def _name(path):
    stem = Path(str(path)).stem.split(' - ')[-1]
    return re.sub(r'[^0-9a-z]', '', stem.lower())


def same_document(a, b, bases):
    """Two datasheet references name one document: equal bytes, or the same part name in the file names."""
    fa, fb = find(a, bases), find(b, bases)
    if fa and fb:
        digest = [hashlib.sha256(f.read_bytes()).hexdigest() for f in (fa, fb)]
        if digest[0] == digest[1]:
            return True
    na, nb = _name(a), _name(b)
    return bool(na) and bool(nb) and (na == nb or na.endswith(nb) or nb.endswith(na))


def design_sheet(comp):
    fields = comp.get('fields') if isinstance(comp.get('fields'), dict) else {}
    return fields.get('DesignSheet') if text(fields.get('DesignSheet')) else None


def touched_refs(contract):
    """Parts this revision adds or changes, per record/change-contract.json; None for a new design."""
    if not isinstance(contract, dict):
        return None
    return set(contract.get('add_components') or {}) | set(contract.get('component_changes') or {})


def audit_identity(intent, bases, touched=None):
    """(problems, inherited): parts of the core or exact class lacking an MPN or a datasheet.

    With a change contract only parts the revision adds or changes are problems; parts kept from the
    baseline are listed as inherited."""
    problems, inherited = [], []
    check_files = library_present()
    for comp in intent.get('components') or []:
        if not isinstance(comp, dict):
            continue
        kind = part_class(comp)
        if kind == SPEC:
            continue
        ref = comp.get('ref')
        sheet = design_sheet(comp) or comp.get('datasheet')
        magnetic = re.match(r'[TL]\d', str(ref or '')) is not None
        lack = []
        if not text(comp.get('mpn')):
            lack.append('料号（mpn）')
        if not text(sheet):
            lack.append('数据手册（datasheet%s）' % ('；定制磁件写 fields.DesignSheet' if magnetic else ''))
        elif check_files and not find(sheet, bases):
            lack.append('能找到的数据手册（%s 不在交付目录或知识库里）' % sheet)
        if not lack:
            continue
        line = '%s %s（%s）缺%s' % (CLASS_NAMES[kind], ref, comp.get('value', ''), '、'.join(lack))
        (problems if touched is None or ref in touched else inherited).append(line)
    return problems, inherited


def audit_citations(intent, closure, bases):
    """Each datasheet cited in a calculation parameter or a data gap names its parts, and they carry that datasheet."""
    comps = {c.get('ref'): c for c in intent.get('components') or [] if isinstance(c, dict)}
    problems = []

    def bound(where, source, refs):
        cited = parse(source)
        # Only a part's datasheet binds to a part; standards and application notes do not.
        if not cited or not cited[0].startswith('Datasheet/'):
            return
        if not refs:
            problems.append('%s 引用了手册 %s，要写明它说的是哪个位号' % (where, cited[0]))
            return
        for ref in refs:
            comp = comps.get(ref)
            if comp is None:
                problems.append('%s 引用手册的位号 %s 不在设计网表里' % (where, ref))
            elif design_sheet(comp):
                continue        # a custom magnetic's design sheet names its core and material datasheets
            elif not text(comp.get('datasheet')):
                problems.append('%s 引用了手册 %s，但设计网表里 %s 没有写 datasheet' % (where, cited[0], ref))
            elif not same_document(comp['datasheet'], cited[0], bases):
                problems.append('%s 引用的手册 %s 与设计网表里 %s 的 datasheet %s 不是同一份'
                                % (where, cited[0], ref, comp['datasheet']))

    for calc in closure.get('calculations') or []:
        for p in (calc.get('parameters') or []) if isinstance(calc, dict) else []:
            if isinstance(p, dict):
                bound('计算 %s 的参数“%s”' % (calc.get('id'), p.get('name')), p.get('source'),
                      [p['ref']] if text(p.get('ref')) else [])
    for item in closure.get('work_items') or []:
        for i, gap in enumerate((item.get('missing') or []) if isinstance(item, dict) else [], 1):
            if isinstance(gap, dict):
                refs = gap.get('refs') if isinstance(gap.get('refs'), list) else []
                bound('待办 %s 的第 %d 项资料缺口' % (item.get('id'), i), gap.get('source'), [r for r in refs if text(r)])
    return problems
