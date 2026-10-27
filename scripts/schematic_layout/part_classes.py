"""Which parts the design netlist must name exactly (references/part-roles.md section 1), aligned with schematic-review.

A part's class follows from its device kind and where it sits, never from a designer's choice. The kind is
declared from the part's own datasheet (``fields.Kind`` with ``KindSource`` and ``KindQuote``) or, for common
parts, read off the symbol and part number and only then the reference prefix (the weakest evidence, as in
schematic-review's ``part_words.classify``). Key parts (ICs, transistors, optocouplers, transformers, zeners,
TVS, bridge rectifiers, custom magnetics) and special parts (safety parts, connectors and relays on nets above
30 V, an NTC in the power path, any part a calculation cites a datasheet for) need an MPN and a datasheet;
common parts are fixed by value and specification, with every capacitor's voltage and every inductor's
current stated. A datasheet cited for a part in a calculation or a data gap must be the datasheet the design
netlist gives that part.
"""

import hashlib
import os
import re
from collections import OrderedDict, namedtuple
from pathlib import Path

from .citations import check, library_present, locate, page_text, parse
from .discrete_semantics import resolve

KEY, SPECIAL, COMMON = 'key', 'special', 'common'
CLASS_NAMES = {KEY: '关键器件', SPECIAL: '特殊器件', COMMON: '常规件'}

Kind = namedtuple('Kind', 'title prefixes words cues')

# The kind vocabulary of schematic-review's scripts/device_kinds.py (plus ASG's `mechanical`). Words are matched
# on "<lib_id> <value> <mpn>" in this order, the first kind wins; prefixes are the weakest evidence. Cues are what a
# datasheet quote must say, lowercase with spaces removed; they include schematic-review's cues for the kind.
KINDS = OrderedDict([
    ('relay', Kind('继电器', ('K',), (r'RELAY|继电器',), ('relay',))),
    ('varistor', Kind('压敏电阻', (), (r'VARISTOR|\bMOV\b|压敏',), ('varistor', 'siov', 'mov'))),
    ('ntc', Kind('热敏电阻', ('TH', 'RT', 'NTC'), (r'NTC|THERMISTOR',),
                 ('ntcthermistor', 'thermistor', 'inrushcurrentlimiter'))),
    ('opto', Kind('光耦', (), (r'OPTO|PC81[07]|LTV\d|TLP\d|6N13[57]|HCPL|ACPL|FOD\d|CNY17|VO6\d|SFH6\d{2,3}|EL8\d\d|'
                             r'PS2[5-9]\d\d|TCMT\d|KPC\d|H11[A-Z]\d|光耦',),
                  ('optocoupler', 'photocoupler', 'optoisolator', 'opticallycoupled', 'opticalisolator', 'opticalcoupler'))),
    ('tvs', Kind('TVS', ('TVS',), (r'TVS|POWER_PROTECTION:|SMAJ|SMBJ|SMCJ|SMF\d|P6KE|1\.5KE|ESD\d|PESD|SM712',),
                 ('tvs', 'esdprotection', 'transientvoltagesuppress', 'transientsuppress'))),
    ('zener', Kind('稳压管', ('ZD',), (r'ZENER|BZX|BZT5\d|MMSZ|1N47\d|稳压二极管',), ('zener',))),
    ('bjt', Kind('双极晶体管', (), (r'TRANSISTOR_BJT:|Q_NPN|Q_PNP|\bNPN\b|\bPNP\b|BC[PXW]?\d{2,3}|2N\d{4}|MMBT|PBSS|S8050|S8550|三极管',),
                 ('npn', 'pnp', 'bipolar'))),
    ('mosfet', Kind('MOSFET', ('Q',), (r'TRANSISTOR_FET:|TRANSISTOR_IGBT:|Q_NMOS|Q_PMOS|MOSFET|\bFET\b|NMOS|PMOS|IRF|IRLML|'
                                       r'AO\d{4}|SI\d{4}|BSS\d|2N7002|IGBT',),
                   ('mosfet', 'nchannel', 'pchannel', 'superjunction', 'igbt'))),
    ('bridge_rectifier', Kind('整流桥', ('BR',), (r'BRIDGE|GBU\d|KBP\d|DB10\d',), ('bridgerectifier', 'bridge'))),
    ('diode', Kind('二极管', ('D', 'LED', 'CR'), (r':D(?:_|\s|$)|:LED|SCHOTTKY|DIODE|SS\d{2}|BAT\d|1N4\d{3}|1N58\d|二极管',),
                   ('rectifier', 'diode', 'schottky', 'led'))),
    ('ferrite', Kind('磁珠', ('FB',), (r'FERRITE|BEAD|BLM\d|MPZ\d|磁珠',), ('ferrite', 'bead'))),
    ('inductor', Kind('电感', ('L', 'FL'), (r':L(?:_|\s|$)|:CMC|INDUCTOR|CHOKE|电感',), ('inductor', 'choke'))),
    ('crystal', Kind('晶体', ('Y', 'X'), (r'CRYSTAL|XTAL|\bOSC(?:ILLATOR)?\b|晶振|晶体',), ('crystal', 'oscillator', 'resonator'))),
    ('transformer', Kind('变压器', ('T', 'TR'), (r'TRANSFORMER|变压器',), ('transformer',))),
    ('fuse', Kind('保险丝', ('F',), (r'FUSE|PTC|保险',), ('fuse', 'ptc', 'resettable', 'polyswitch'))),
    ('battery', Kind('电池', ('BT', 'BAT'), (r'(?:^|[\s:_])BATTERY|电池',), ('battery',))),
    ('testpoint', Kind('测试点', ('TP',), (r'TEST_?POINT|TEST-?PAD',), ('testpoint',))),
    ('connector', Kind('连接器', ('J', 'P', 'CN'), (r'CONNECTOR[A-Z_]*:|CONN_\d|USB_C_|RECEPTACLE|BARREL_?JACK|PINHEADER|'
                                               r'TERMINAL_?BLOCK|SCREW_TERMINAL',),
                       ('connector', 'receptacle', 'terminalblock', 'terminal', 'header', 'jack', 'plug', 'socket'))),
    ('switch', Kind('开关', ('SW', 'S'), (r':SW_|SWITCH:|KEYSW|:MX-',), ('switch',))),
    ('jumper', Kind('跳线', ('JP',), (r'JUMPER',), ('jumper',))),
    ('mechanical', Kind('机械件', ('H', 'MH', 'MB', 'FID', 'LOGO', 'HS'), (r'MOUNTINGHOLE|FIDUCIAL|HEATSINK|MECHANICAL:',), ())),
    ('capacitor', Kind('电容', ('C', 'CX', 'CY'), (r':C(?:_|\s|$)|:CP(?:_|\d*(?:\s|$))|CAPACITOR',),
                       ('capacitor', 'x1', 'x2', 'y1', 'y2'))),
    ('resistor', Kind('电阻', ('R', 'RN'), (r':R(?:_|\s|$)|RESISTOR|POTENTIOMETER',), ('resistor',))),
    ('ic', Kind('集成电路', ('U', 'M', 'IC', 'A', 'MODULE', 'REF'), (), ())),
])
KEY_KINDS = ('ic', 'mosfet', 'bjt', 'opto', 'transformer', 'zener', 'tvs', 'bridge_rectifier')
IC_PREFIXES = KINDS['ic'].prefixes
# A more specific declared kind than the symbol shows is not a conflict.
REFINES = {'diode': ('tvs', 'zener'), 'inductor': ('transformer', 'ferrite')}
SAFETY_CLASS = re.compile(r'(?<![A-Za-z0-9])[XY][12](?![A-Za-z0-9])')
VOLTAGE = re.compile(r'\d\s*k?V(?![A-Za-z])|\d\s*k?V(?:ac|dc|AC|DC|rms)', re.I)
CURRENT = re.compile(r'\d\s*m?A(?![A-Za-z])|\d\s*m?A(?:rms|pk|dc)', re.I)


def prefix(comp):
    return re.match(r'[A-Z]*', str(comp.get('ref', '')).upper()).group()


def fields(comp):
    return comp.get('fields') if isinstance(comp.get('fields'), dict) else {}


def inferred_kind(comp):
    """(kind, basis) from the symbol and part number ('symbol'), then the reference prefix ('prefix'); (None, None)."""
    blob = ' '.join(str(comp.get(k) or '') for k in ('lib_id', 'value', 'mpn')).upper()
    ic_ref = prefix(comp) in IC_PREFIXES
    named = [name for name, kind in KINDS.items() for w in kind.words if re.search(w, blob, re.I)]
    if {'bjt', 'mosfet'} <= set(named):
        named = [n for n in named if n not in ('bjt', 'mosfet')]
    for name in named:
        # An IC's text names other kinds ("charger with NTC input", CP2102): only a key kind re-identifies it.
        if not ic_ref or name in KEY_KINDS:
            return name, 'symbol'
    for name, kind in KINDS.items():
        if prefix(comp) in kind.prefixes:
            return name, 'prefix'
    return None, None


def kind_of(comp):
    """(kind, problem): the declared kind when it is a known kind and agrees with the symbol, else the inferred one."""
    declared = fields(comp).get('Kind')
    inferred, basis = inferred_kind(comp)
    if not text(declared):
        return inferred, None
    if declared not in KINDS:
        return inferred, 'fields.Kind 写的 %s 不是器件类型（可选：%s）' % (declared, '、'.join(KINDS))
    if basis == 'symbol' and inferred != declared and declared not in REFINES.get(inferred, ()):
        return declared, '类型声明 %s 与符号或型号 %s 推断的 %s 不一致（选错了符号或填错了型号）' % (
            declared, comp.get('lib_id') or comp.get('value'), inferred)
    return declared, None


def context(intent):
    """Nets of each part, the net roles and the declared high-voltage nets (None when not declared)."""
    nets = intent.get('nets') or []
    items = nets.items() if isinstance(nets, dict) else ((n.get('name'), n.get('pins')) for n in nets if isinstance(n, dict))
    pins = {}
    for name, members in items:
        for pin in members or []:
            pins.setdefault(str(pin).rsplit('.', 1)[0], set()).add(name)
    hv = intent.get('high_voltage_nets')
    return {'pins': pins, 'roles': intent.get('net_roles') or {}, 'hv': set(hv) if isinstance(hv, list) else None}


def part_class(comp, ctx=None):
    """key / special / common for one design-netlist component, or None when its kind is not known."""
    ctx = ctx or {'pins': {}, 'roles': {}, 'hv': None}
    kind, _ = kind_of(comp)
    if kind is None:
        return None
    nets = ctx['pins'].get(comp.get('ref'), set())
    high = ctx['hv'] is None or bool(nets & ctx['hv'])
    if design_sheet(comp) and kind in ('inductor', 'transformer'):
        return KEY
    if kind in KEY_KINDS:
        return KEY
    if kind in ('varistor', 'fuse'):
        return SPECIAL
    if kind == 'capacitor' and (prefix(comp) in ('CX', 'CY') or SAFETY_CLASS.search(
            '%s %s' % (comp.get('value') or '', fields(comp).get('Specification') or ''))):
        return SPECIAL
    if kind in ('connector', 'relay') and high:
        return SPECIAL
    if kind == 'ntc' and (high or (nets and all(ctx['roles'].get(n) in ('power', 'return') for n in nets))):
        return SPECIAL
    return COMMON


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
    sheet = fields(comp).get('DesignSheet')
    return sheet if text(sheet) else None


def touched_refs(contract):
    """Parts this revision adds or changes, per record/change-contract.json; None for a new design."""
    if not isinstance(contract, dict):
        return None
    return set(contract.get('add_components') or {}) | set(contract.get('component_changes') or {})


def _squash(value):
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]', '', str(value or '').lower())


def declaration_lack(comp, kind, bases, check_files):
    """What a key or special part's kind declaration lacks: fields.Kind, its own datasheet page, a quote naming the kind."""
    f = fields(comp)
    if not text(f.get('Kind')):
        return ['类型声明（fields.Kind、KindSource、KindQuote，按本器件手册）']
    lack = []
    cited = parse(f.get('KindSource'))
    if not cited:
        lack.append('类型声明的手册页（fields.KindSource 写 datasheet:<库内路径>#p<页>）')
    elif text(comp.get('datasheet')) and not same_document(comp['datasheet'], cited[0], bases):
        lack.append('类型声明引用本器件的手册（KindSource %s 与 datasheet %s 不是同一份）' % (cited[0], comp['datasheet']))
    elif check_files:
        result = check(cited[0], cited[1], (), bases)
        if result['status'] == 'FAIL':
            lack.append('能核对的类型声明手册页（%s）' % result['reason'])
    quote = _squash(f.get('KindQuote'))
    if not quote:
        lack.append('类型声明的手册原文（fields.KindQuote）')
    elif KINDS[kind].cues and not any(c in quote for c in KINDS[kind].cues):
        lack.append('说出类型的手册原文（KindQuote 没有说出 %s）' % kind)
    elif cited and check_files:
        pdf = locate(cited[0], bases)
        page = _squash(page_text(pdf, cited[1])) if pdf else ''
        if len(page) > 100 and quote not in page:
            lack.append('手册上的原文（KindQuote 不在 %s 第 %d 页）' % (cited[0], cited[1]))
    return lack


def audit_identity(intent, bases, touched=None):
    """(problems, inherited): parts whose kind is unknown or contradicted, key and special parts lacking an MPN,
    a datasheet or a kind declaration, and common capacitors and inductors without their rating.

    With a change contract only parts the revision adds or changes are problems; parts kept from the
    baseline are listed as inherited."""
    problems, inherited = [], []
    check_files = library_present()
    ctx = context(intent)
    for comp in intent.get('components') or []:
        if not isinstance(comp, dict):
            continue
        ref = comp.get('ref')
        kind, conflict = kind_of(comp)
        kind_cls = part_class(comp, ctx)
        lack = [conflict] if conflict else []
        if kind is None:
            lack.append('器件类型（认不出，写 fields.Kind：%s）' % '、'.join(KINDS))
        elif kind_cls in (KEY, SPECIAL):
            sheet = design_sheet(comp) or comp.get('datasheet')
            magnetic = kind in ('inductor', 'transformer')
            if not text(comp.get('mpn')):
                lack.append('料号（mpn）')
            if not text(sheet):
                lack.append('数据手册（datasheet%s）' % ('；定制磁件写 fields.DesignSheet' if magnetic else ''))
            elif check_files and not find(sheet, bases):
                lack.append('能找到的数据手册（%s 不在交付目录或知识库里）' % sheet)
            if kind != 'ic' and not design_sheet(comp):
                lack += declaration_lack(comp, kind, bases, check_files)
        else:
            rating = '%s %s %s' % (comp.get('value') or '', fields(comp).get('Specification') or '', fields(comp).get('Rating') or '')
            if kind == 'capacitor' and not VOLTAGE.search(rating):
                lack.append('耐压（写在值或 fields.Specification 里）')
            if kind == 'inductor' and not CURRENT.search(rating):
                lack.append('额定电流（写在值或 fields.Specification 里）')
        if not lack:
            continue
        lack = [x for x in lack if x != conflict]
        said = ([conflict] if conflict else []) + (['缺' + '、'.join(lack)] if lack else [])
        line = '%s %s（%s）%s' % (CLASS_NAMES.get(kind_cls, '器件'), ref, comp.get('value', ''), '；'.join(said))
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
            elif not text(comp.get('mpn')):
                problems.append('%s 引用了手册 %s，%s 因此是特殊器件，设计网表里要写它的 mpn' % (where, cited[0], ref))
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
