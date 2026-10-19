#!/usr/bin/env python3
"""Write 设计报告.md for one delivery folder from its own records.

Every number and status comes from <delivery>/record/; the agent adds plain-language
text only through notes.json {summary, changes, items{work_id: text}, highlights[≤8]}.
Records that are missing or inconsistent are reported at the top instead of guessed.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schematic_layout.sexpr import all_nodes, first, parse  # noqa: E402

REPORT = '设计报告.md'
SEVERITIES = ('P0', 'P1', 'P2', 'P3')
SEVERITY_WORDS = {'P0': '可能损坏器件或危及安全', 'P1': '必需功能可能不达标',
                  'P2': '局部或次要问题', 'P3': '可选优化'}
SEVERITY_LEGEND = '可能后果：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。'
GATES = OrderedDict([
    ('erc', 'KiCad 电气规则检查（ERC）'),
    ('intent_netlist', '网表与设计要求表逐脚对照'),
    ('hierarchy', '图纸层次与页数'),
    ('system_block', '系统框图（箭头标注、隔离边界、无悬空线）'),
    ('symbol_integrity', '符号引脚完整'),
    ('discrete_semantics', '分立器件符号与手册一致（TVS单/双向、MOS沟道、NPN/PNP）'),
    ('readability', '图面可读性'),
    ('geometry', '图面几何（重叠、穿线）'),
    ('external_supply', '外部供电声明'),
    ('reference_contract', '外围电路按手册核对'),
    ('design_change', '改动与预期一致'),
])
GATE_RESULTS = OrderedDict([('PASS', '通过（PASS）'), ('FAIL', '没通过（FAIL）'),
                            ('INSUFFICIENT', '资料不足（INSUFFICIENT）'), ('CONDITIONAL', '有条件通过')])
VISUAL = {'REVIEWED': '已完成', 'REVIEW_PENDING': '还没做完', 'REWORK_REQUIRED': '发现要返工的地方'}
STAGES = {'requirement': '等用户定需求', 'design': '设计没做完', 'external': '缺外部资料', 'validation': '样机或试验验证', 'pcb': 'PCB 实现'}
REQUIREMENTS = OrderedDict([('design_supported', '有设计依据'), ('conditional', '有条件成立'), ('open', '还没有设计')])
RESPONSES = OrderedDict([
    ('REDESIGN', ('改图', 'changes')), ('CALC_DOC', ('补计算/补文档', 'changes')), ('DESIGN', ('补设计', 'work_items')),
    ('OBTAIN_DATA', ('补资料', 'work_items')), ('ASK_USER', ('请用户定需求', 'detail')),
    ('HANDOFF', ('交给后续环节', 'work_items')), ('DECLINE', ('不采纳', 'evidence')),
    ('DEFERRED', ('已暂缓', 'detail'))])
RESPONSE_STAGE = {'ASK_USER': ('requirement',), 'DESIGN': ('design',), 'OBTAIN_DATA': ('external',), 'HANDOFF': ('validation', 'pcb')}
REF_PATTERN = re.compile(r'(?<![A-Za-z0-9])[A-Z]{1,3}\d{1,4}(?![A-Za-z0-9])')
PAGE_PATTERN = re.compile(r'(?<![A-Za-z0-9])\d{2}_[A-Za-z][A-Za-z0-9_]*|System_block')
# Words that describe the review process, not a design basis.
PROCESS_WORDS = ('审查', '第一轮', '第二轮', '下一轮', '下一版', '核销', '复审')
REQUIRED = ('electrical-intent.json', 'design-closure.json', 'design-closure-audit.json',
            'summary.json', 'visual-review.json', 'page-plan.json', 'selection.json', 'lessons.json')
CAUSES = ('rule_missing', 'rule_not_enforced', 'knowledge_missing', 'knowledge_wrong', 'judgment')
CAUSE_WORDS = {'rule_missing': '缺规则', 'rule_not_enforced': '规则没执行', 'knowledge_missing': '缺知识',
               'knowledge_wrong': '知识有错', 'judgment': '判断失误', 'none': '无需改'}
# Where a change for each cause class must land: rules become gates, knowledge goes to references or the library.
CAUSE_TARGETS = {'rule_missing': ('scripts/',), 'rule_not_enforced': ('scripts/',),
                 'knowledge_missing': ('references/', 'wiki/', 'raw/'), 'knowledge_wrong': ('references/', 'wiki/', 'raw/'),
                 'judgment': ('SKILL.md', 'references/')}
SOURCE_PATTERN = re.compile(r'^(review:[^/\s]+/\S+|datasheet:.+#p\d+|test:\S+|user:\d{4}-\d{2}-\d{2})$')
PAGE_REF = re.compile(r'(p\.?\s?\d+|第\s?\d+\s?页|W-[A-Z0-9-]+)')
SELECTION_STATUS = ('selected', 'rejected', 'alternate')
OPS = ('<=', '>=', 'covers', 'equals', 'has')
# A rejection that is not a failed decisive condition must say what kind it is.
REJECT_KINDS = {'dependency': '依赖拿不到', 'data': '资料不足', 'availability': '可得性', 'cost': '成本',
                'preference': '都能用，按优先规则落选'}
CORE_REF = re.compile(r'^[UQT]\d')


def text(value):
    return isinstance(value, str) and bool(value.strip())


OPERATOR_SIGNS = {'<=': '≤', '<': '<', '>=': '≥', '>': '>'}
SIDE_WORDS = {'no_false_trip': '不误动作', 'protection': '能保护'}


def english_sentence(value):
    """Prose written in English rather than Chinese. Part numbers, units and
    all-caps acronyms (PFC, OVP, NTC) are allowed inside Chinese text."""
    if not text(value):
        return False
    words = [w for w in re.findall(r'(?<![A-Za-z0-9])[A-Za-z]{3,}(?![A-Za-z0-9])', value) if not w.isupper()]
    cjk = len(re.findall(r'[\u4e00-\u9fff]', value))
    return len(words) >= 4 and cjk < 2 * len(words)


def check_language(closure, notes):
    """Everything the report shows to engineers is written in Chinese."""
    found = []
    def scan(where, value):
        if english_sentence(value):
            found.append('%s：“%s”' % (where, value.strip()[:40] + ('…' if len(value.strip()) > 40 else '')))
    for c in closure.get('calculations') or []:
        if not isinstance(c, dict):
            continue
        for field, word in (('assumptions', '假设'), ('omitted_terms', '没算进去的项')):
            for i, v in enumerate(c.get(field) or []):
                scan('计算 %s %s %d' % (c.get('id'), word, i + 1), v)
        for i, chk in enumerate(c.get('checks') or []):
            if isinstance(chk, dict):
                scan('计算 %s 核对项 %d' % (c.get('id'), i + 1), chk.get('name'))
    for w in closure.get('work_items') or []:
        if isinstance(w, dict):
            for field in ('action', 'owner', 'fallback', 'assumption'):
                scan('待办 %s %s' % (w.get('id'), field), w.get(field))
    for r in closure.get('requirements') or []:
        if isinstance(r, dict):
            scan('需求 %s 实现说明' % r.get('id'), r.get('implementation'))
    for field in ('summary', 'changes'):
        scan('notes %s' % field, notes.get(field))
    for key, v in (notes.get('items') or {}).items():
        scan('notes 待办 %s' % key, v)
    for i, v in enumerate(notes.get('highlights') or []):
        scan('notes 关键依据 %d' % (i + 1), v)
    if not found:
        return []
    return ['下列给人看的文字是英文，要改成中文（器件型号、单位和缩写可以保留）：' + '；'.join(found[:6])
            + ('；等共 %d 处' % len(found) if len(found) > 6 else '')]


def symbol_refs(sch_path):
    """Placed symbol uuid -> reference, from one native sheet."""
    refs = {}
    for sym in all_nodes(parse(sch_path.read_text(encoding='utf-8')), 'symbol'):
        uid = first(sym, 'uuid')
        ref = next((str(p[2]) for p in all_nodes(sym, 'property') if len(p) > 2 and p[1] == 'Reference'), None)
        if uid and len(uid) > 1 and ref:
            refs[str(uid[1])] = ref
    return refs


PATTERNS_DIR = Path(__file__).resolve().parent.parent / 'references' / 'circuit-patterns'


def pattern_approaches(patterns_dir=PATTERNS_DIR):
    out = {}
    for md in sorted(patterns_dir.glob('*.md')) if patterns_dir.is_dir() else []:
        out[md.stem] = {line[4:].strip() for line in md.read_text(encoding='utf-8').splitlines() if line.startswith('### ')}
    return out


def check_block_patterns(name, blocks, patterns, approaches, lessons):
    """Each functional block names an existing pattern approach, or lessons.json registers the gap."""
    errors = []
    registered = any(isinstance(e, dict) and e.get('cause') == 'knowledge_missing' and 'circuit-patterns' in str(e.get('change') or '')
                     for e in (lessons or {}).get('events') or [])
    patterns = patterns if isinstance(patterns, dict) else {}
    for block in blocks:
        ref = patterns.get(block)
        if not text(ref):
            if not registered:
                errors.append('%s：功能块“%s”没有标注电路模式（patterns），没有合适模式时在 lessons.json 登记 knowledge_missing 并补写 references/circuit-patterns/' % (name, block))
            continue
        pid, _, approach = ref.partition('#')
        if pid not in approaches:
            errors.append('%s：功能块“%s”标注的模式 %s 在 references/circuit-patterns/ 里不存在' % (name, block, pid))
        elif approach not in approaches[pid]:
            errors.append('%s：功能块“%s”标注的做法“%s”不在模式 %s 里（有：%s）' % (name, block, approach, pid, '、'.join(sorted(approaches[pid]))))
    return errors


def check_page_plan(plan, intent, visual, lessons=None, patterns_dir=PATTERNS_DIR):
    """Every drawn page has a plan (reader tasks, blocks of parts, the pattern of each block) and a review that traced each task."""
    if not isinstance(plan, dict) or plan.get('schema_version') != 1 or not isinstance(plan.get('pages'), list):
        return ['page-plan.json 必须是 schema_version 1、带 pages 列表的对象']
    errors = []
    approaches = pattern_approaches(patterns_dir)
    known = {c.get('ref') for c in intent.get('components') or [] if isinstance(c, dict)}
    on_page = {}
    for c in intent.get('components') or []:
        if isinstance(c, dict) and isinstance(c.get('fields'), dict) and text(c['fields'].get('Circuit')):
            on_page.setdefault(c['fields']['Circuit'], set()).add(c.get('ref'))
    reviewed = {p.get('file'): p for p in (visual.get('pages') or []) if isinstance(p, dict)}
    for index, page in enumerate(plan['pages']):
        name = page.get('file') if isinstance(page, dict) else None
        if not text(name):
            errors.append('page-plan.json 有一页没有 file')
            continue
        tasks = page.get('reader_tasks')
        blocks = page.get('blocks')
        if not isinstance(tasks, list) or not tasks or not all(text(t) for t in tasks):
            errors.append('%s：要写明读者任务（reader_tasks）' % name)
        if not isinstance(blocks, dict) or not blocks or not all(isinstance(v, list) and v for v in blocks.values()):
            errors.append('%s：要按功能块列出器件（blocks）' % name)
            continue
        placed = {}
        for block, refs in blocks.items():
            for ref in refs:
                if ref not in known:
                    errors.append('%s：功能块“%s”里的 %s 不在设计要求表里' % (name, block, ref))
                elif ref in placed:
                    errors.append('%s：%s 同时在功能块“%s”和“%s”里' % (name, ref, placed[ref], block))
                placed[ref] = block
        cover = index == 0 and len(plan['pages']) > 1          # the first page is the System_block cover (SKILL.md step 1)
        if not cover and 'system_block' not in name.lower():
            errors += check_block_patterns(name, blocks, page.get('patterns'), approaches, lessons)
        missing = sorted(on_page.get(Path(name).stem, set()) - set(placed))
        if missing:
            errors.append('%s：这些器件不属于任何功能块：%s' % (name, '、'.join(missing[:6])))
        review = reviewed.get(name)
        if review is None:
            errors.append('%s：看图检查没有这一页的记录' % name)
        elif isinstance(tasks, list) and len(review.get('paths') or []) < len(tasks):
            errors.append('%s：读者任务 %d 条，看图检查只追了 %d 条路径' % (name, len(tasks), len(review.get('paths') or [])))
    return errors


def check_visual_items(root, visual):
    """Pin-text items handed to the render review are dispositioned per symbol, naming what was seen."""
    errors = []
    for page in visual.get('pages') or []:
        items = page.get('render_review_items') if isinstance(page, dict) else None
        if not items:
            continue
        name = page.get('file')
        sch = root / '原理图' / str(name)
        if not text(name) or not sch.is_file():
            errors.append('第 %s 页：有引脚文字条目但找不到原理图/%s' % (page.get('page'), name))
            continue
        try:
            refs = symbol_refs(sch)
        except (OSError, ValueError) as error:
            errors.append('原理图/%s 读不出来：%s' % (name, error))
            continue
        by_text = {}
        for item in items:
            key = str(item.get('item', '')) if isinstance(item, dict) else ''
            parts = key.split(':')
            ref = refs.get(parts[1]) if len(parts) > 1 else None
            disposition = item.get('disposition', '') if isinstance(item, dict) else ''
            if ref is None:
                errors.append('%s：条目“%s”的符号在图里找不到' % (name, key[:48]))
            elif not text(disposition) or ref not in disposition:
                errors.append('%s：%s 的引脚文字处置要写明在图上看到了什么，并点名 %s' % (name, ref, ref))
            else:
                by_text.setdefault(disposition, set()).add(ref)
        for disposition, group in by_text.items():
            if len(group) > 1:
                errors.append('%s：同一句处置用在了 %s：要逐个器件写看到了什么' % (name, '、'.join(sorted(group))))
    return list(OrderedDict.fromkeys(errors))  # one line per symbol, not per pin


def norm_mpn(value):
    return re.sub(r'[\s\-_/]+', '', value if text(value) else '').lower()


def judge(cond, entry):
    """(ok, shown) for one decisive condition against one candidate's recorded value; ok is None when unusable."""
    op, limit = cond.get('op'), cond.get('limit')
    if not isinstance(entry, dict) or 'value' not in entry or not (text(entry.get('page')) or isinstance(entry.get('page'), int)):
        return None, '没有值或页码'
    value = entry['value']
    unit = cond.get('unit') or ''
    try:
        if op in ('<=', '>='):
            ok = float(value) <= float(limit) if op == '<=' else float(value) >= float(limit)
            return ok, '%s %s %s %s' % (num(value), op, num(limit), unit)
        if op == 'covers':
            ok = float(value[0]) <= float(limit[0]) and float(value[1]) >= float(limit[1])
            return ok, '%s–%s 覆盖 %s–%s %s' % (num(value[0]), num(value[1]), num(limit[0]), num(limit[1]), unit)
        if op == 'equals':
            return norm_mpn(str(value)) == norm_mpn(str(limit)), '%s = %s' % (value, limit)
        if op == 'has':
            want = limit if isinstance(limit, bool) else True
            return bool(value) == want, '%s%s' % ('有' if value else '无', '' if want else '（要求无）')
    except (TypeError, ValueError, IndexError):
        pass
    return None, '值 %r 无法按 %s 判定' % (value, op)


def check_conditions(name, conds, cands):
    """Selected and alternate candidates satisfy every decisive condition; a rejected one fails at least one or says why."""
    problems, basis = [], []
    for c in cands:
        mpn = c.get('mpn') if text(c.get('mpn')) else '?'
        verdicts = [(d['param'], *judge(d, (c.get('values') or {}).get(d['param']))) for d in conds]
        failed = [(param, shown) for param, ok, shown in verdicts if ok is False]
        if c.get('status') in ('selected', 'alternate'):
            for param, ok, shown in verdicts:
                if ok is None:
                    problems.append('选型角色“%s”候选 %s 没有给出条件“%s”的值和页码（%s）' % (name, mpn, param, shown))
                elif not ok:
                    problems.append('选型角色“%s”候选 %s 不满足条件“%s”（%s）却被%s' % (name, mpn, param, shown, '选定' if c.get('status') == 'selected' else '列为备选'))
        else:
            kind = c.get('reject_kind')
            if failed:
                basis.append('%s：%s %s' % (mpn, failed[0][0], failed[0][1]))
            elif kind in REJECT_KINDS:
                basis.append('%s：%s' % (mpn, REJECT_KINDS[kind]))
            else:
                problems.append('选型角色“%s”淘汰候选 %s 没有一条决定性条件判定不满足，也没写 reject_kind（%s）'
                                % (name, mpn, '/'.join(REJECT_KINDS)))
    return problems, basis


def check_selection(data, intent, root):
    """Every core part was chosen from compared candidates whose datasheets are in the library."""
    roles = data.get('roles') if isinstance(data, dict) else None
    if not isinstance(roles, list) or not roles:
        return ['selection.json 没有 roles：每个核心器件角色都要有候选比较（见 core-part-selection.md）']
    problems = []
    comps = {c.get('ref'): c for c in intent.get('components') or [] if isinstance(c, dict)}
    library = Path(os.path.expanduser(data.get('library_root') if text(data.get('library_root')) else ''))
    covered = set()
    for i, role in enumerate(roles, 1):
        if not isinstance(role, dict):
            problems.append('selection.json 第 %d 个角色不是对象' % i)
            continue
        name = role.get('role') if text(role.get('role')) else '第 %d 个角色' % i
        refs = [r for r in role.get('refs') or [] if text(r)]
        cands = [c for c in role.get('candidates') or [] if isinstance(c, dict)]
        for key, label in (('refs', '位号'), ('decisive', '决定性条件'), ('sources', '候选来源')):
            if not role.get(key):
                problems.append('选型角色“%s”没有写%s' % (name, label))
        conds = [d for d in role.get('decisive') or [] if isinstance(d, dict)]
        if role.get('decisive') and (len(conds) != len(role['decisive']) or not all(
                text(d.get('param')) and d.get('op') in OPS and 'limit' in d for d in conds)):
            problems.append('选型角色“%s”的决定性条件要写成 {param, op, limit[, unit, requirement]}，op 取 %s' % (name, '/'.join(OPS)))
            conds = []
        if conds:
            cond_problems, basis = check_conditions(name, conds, cands)
            problems += cond_problems
            role['_basis'] = basis
        if len(cands) < 2 and not text(role.get('single_candidate_reason')):
            problems.append('选型角色“%s”只有 %d 个候选又没写 single_candidate_reason' % (name, len(cands)))
        selected = [c for c in cands if c.get('status') == 'selected']
        if len(selected) != 1:
            problems.append('选型角色“%s”要恰好一个 selected 候选，现在 %d 个' % (name, len(selected)))
        for c in cands:
            mpn = c.get('mpn') if text(c.get('mpn')) else '?'
            if c.get('status') not in SELECTION_STATUS:
                problems.append('候选 %s 的 status 必须是 %s 之一' % (mpn, '/'.join(SELECTION_STATUS)))
            if not text(c.get('reason')):
                problems.append('候选 %s 没有写选中或淘汰的理由' % mpn)
            sheet = c.get('datasheet') if text(c.get('datasheet')) else ''
            if not sheet or not ((library / sheet).is_file() or (root / sheet).is_file()):
                problems.append('候选 %s 的资料 %s 不在知识库 %s 或交付目录内' % (mpn, sheet or '（没写）', library))
        for ref in refs:
            covered.add(ref)
            if ref not in comps:
                problems.append('选型角色“%s”的位号 %s 不在设计要求表里' % (name, ref))
            elif selected:
                mpn = selected[0].get('mpn') if text(selected[0].get('mpn')) else ''
                value = next((comps[ref][k] for k in ('value', 'mpn') if text(comps[ref].get(k))), '')
                if norm_mpn(mpn) not in norm_mpn(value):
                    problems.append('位号 %s 的 value “%s” 不含选定型号 %s' % (ref, value, mpn))
    missing = sorted(r for r in comps if CORE_REF.match(r if text(r) else '') and r not in covered)
    if missing:
        problems.append('核心器件没有选型记录：%s' % '、'.join(missing))
    return problems


def check_lessons(data):
    """What this version taught the skill: each event has a source, a cause class and a concrete change."""
    events = data.get('events') if isinstance(data, dict) else None
    if not isinstance(events, list) or not events:
        return ['lessons.json 没有 events：每次设计至少登记一条学到的东西，没有就登记 cause=none 并写明核对了什么'], {}
    problems, by_source = [], {}
    for i, e in enumerate(events, 1):
        if not isinstance(e, dict):
            problems.append('lessons.json 第 %d 条不是对象' % i)
            continue
        source = e.get('source') if text(e.get('source')) else ''
        if not SOURCE_PATTERN.match(source):
            problems.append('lessons.json 第 %d 条的 source 要写成 review:<审查目录>/<待办编号>、datasheet:<库内路径>#p<页>、test:<记录> 或 user:<日期>' % i)
        else:
            by_source[source] = e
        cause = e.get('cause')
        if cause not in CAUSES and cause != 'none':
            problems.append('lessons.json 第 %d 条的 cause 必须是 %s 或 none' % (i, '/'.join(CAUSES)))
            continue
        if cause == 'none':
            why = e.get('why_none') if text(e.get('why_none')) else ''
            if not PAGE_REF.search(why):
                problems.append('lessons.json 第 %d 条 cause=none 要在 why_none 里引用核对过的页码或待办编号' % i)
            continue
        change = e.get('change') if text(e.get('change')) else ''
        if not any(t in change for t in CAUSE_TARGETS[cause]):
            problems.append('lessons.json 第 %d 条归因 %s，change 要指向 %s 下的具体文件' % (i, cause, '/'.join(CAUSE_TARGETS[cause])))
        if cause == 'judgment' and not text(e.get('why_not_rule')):
            problems.append('lessons.json 第 %d 条归因 judgment 要写 why_not_rule：为什么规则和知识都拦不住' % i)
    return problems, by_source


def num(value):
    """A number with three significant digits; integers and non-numbers unchanged."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, int) or value == 0 or value != value:
        return str(value)
    rounded = float('%.3g' % value)
    return str(int(rounded)) if rounded == int(rounded) and abs(rounded) >= 1 else ('%f' % rounded).rstrip('0').rstrip('.')


def check_text(chk):
    if not isinstance(chk, dict):
        return ''
    side = SIDE_WORDS.get(chk.get('side'))
    return '%s%s：%s %s %s %s' % ('[%s] ' % side if side else '', chk.get('name'), num(chk.get('value')),
                                 OPERATOR_SIGNS.get(chk.get('operator'), chk.get('operator')),
                                 num(chk.get('limit')), chk.get('unit') or '')


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').strip()


def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return None, '缺少 record/%s' % path.name
    except (OSError, ValueError) as error:
        return None, 'record/%s 读不出来：%s' % (path.name, error)


def check_responses(data, work, intent=None, closure=None, root=None, lessons=None):
    """Each review comment has one allowed response and what that response requires.

    A response is work done this version, not a transcription of the comment:
    the same explanation may not serve several comments, 补设计 points at a
    work item that records this version's progress, 改图 names the parts it
    changed, and 补计算/补文档 names the calculation or design document.
    """
    errors = []
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        return ['review-responses.json 必须是 schema_version 1 的对象']
    known_refs = {c.get('ref') for c in (intent or {}).get('components') or [] if isinstance(c, dict)}
    calc_ids = {c.get('id') for c in (closure or {}).get('calculations') or [] if isinstance(c, dict)}
    details = Counter(i.get('detail') for i in data.get('items') or [] if isinstance(i, dict) and text(i.get('detail')))
    for detail, n in details.items():
        if n > 1:
            errors.append('处理说明“%s”在 %d 条意见里重复：每条意见要写它自己怎么处理' % (detail[:30] + ('…' if len(detail) > 30 else ''), n))
    sources = {s.get('id') for s in data.get('sources') or [] if isinstance(s, dict)
               and text(s.get('id')) and text(s.get('path')) and text(s.get('sha256'))}
    if not sources:
        errors.append('review-responses.json 没有登记意见来源（id、path、sha256）')
    seen = set()
    for item in data.get('items') or []:
        key = item.get('id') if isinstance(item, dict) else None
        if not text(key) or key in seen:
            errors.append('审查意见编号缺失或重复：%s' % key)
            continue
        seen.add(key)
        response = item.get('response')
        if response not in RESPONSES:
            errors.append('%s：处理方式必须是 %s 之一' % (key, '/'.join(RESPONSES)))
            continue
        if item.get('source') not in sources or not text(item.get('locator')) or not text(item.get('comment')):
            errors.append('%s：要写明来源、在原文中的位置和意见内容' % key)
        if not text(item.get('detail')):
            errors.append('%s：要说明怎么处理、为什么' % key)
        if lessons is not None:
            cause = item.get('cause')
            if cause not in CAUSES and cause != 'none':
                errors.append('%s：要归因（cause）：%s 或 none' % (key, '/'.join(CAUSES)))
            elif cause != 'none':
                event = next((e for src, e in lessons.items() if src.startswith('review:') and src.endswith('/' + key)), None)
                if event is None:
                    errors.append('%s：归因 %s，lessons.json 里要有 source 以 /%s 结尾的事件写明改了什么' % (key, cause, key))
                elif event.get('cause') != cause:
                    errors.append('%s：review-responses 归因 %s，lessons.json 同一事件归因 %s，要一致' % (key, cause, event.get('cause')))
        field = RESPONSES[response][1]
        if field != 'detail' and not (isinstance(item.get(field), list) and item[field]):
            errors.append('%s：处理方式为“%s”时必须填 %s' % (key, RESPONSES[response][0], field))
        changes = [c for c in item.get('changes') or [] if text(c)]
        if response == 'REDESIGN' and changes and not any(
                (known_refs & set(REF_PATTERN.findall(c))) or PAGE_PATTERN.search(c) for c in changes):
            errors.append('%s：“改图”的 changes 没有点名改了哪个位号或哪一页' % key)
        if response == 'CALC_DOC':
            for c in changes:
                if c not in calc_ids and not (root is not None and (Path(root) / '设计资料' / c).is_file()):
                    errors.append('%s：“补计算/补文档”的 changes 项“%s”既不是计算编号也不是设计资料文件' % (key, c[:30]))
        for wid in item.get('work_items') or []:
            row = work.get(wid)
            if row is None:
                errors.append('%s：引用的待办 %s 不在 design-closure.json 里' % (key, wid))
            elif response in RESPONSE_STAGE and row.get('stage') not in RESPONSE_STAGE[response]:
                errors.append('%s：待办 %s 的阶段与处理方式“%s”不符' % (key, wid, RESPONSES[response][0]))
            elif response == 'DESIGN' and row.get('status') != 'closed' and (
                    not text(row.get('progress')) or row.get('progress') == row.get('action')):
                errors.append('%s：“补设计”引用的待办 %s 没有写本版做了什么（progress），只抄了意见' % (key, wid))
    if not seen:
        errors.append('review-responses.json 没有登记任何意见')
    return errors


def worst(levels):
    found = [s for s in SEVERITIES if s in levels]
    return found[0] if found else None


def render(root, notes=None, title=None):
    root = Path(root)
    record = root / 'record'
    notes = notes or {}
    problems = []
    data = {}
    for name in REQUIRED:
        data[name], problem = load(record / name)
        if problem:
            problems.append(problem)
    intent = data['electrical-intent.json'] or {}
    closure = data['design-closure.json'] or {}
    audit = data['design-closure-audit.json'] or {}
    summary = data['summary.json'] or {}
    visual = data['visual-review.json'] or {}
    responses, change = None, None
    if (record / 'review-responses.json').exists():
        responses, problem = load(record / 'review-responses.json')
        if problem:
            problems.append(problem)
    if (record / 'design-change.json').exists():
        change, problem = load(record / 'design-change.json')
        if problem:
            problems.append(problem)

    work = {w['id']: w for w in closure.get('work_items') or [] if isinstance(w, dict) and text(w.get('id'))}
    requirements = [r for r in closure.get('requirements') or [] if isinstance(r, dict)]
    calculations = [c for c in closure.get('calculations') or [] if isinstance(c, dict)]
    if audit and audit.get('status') == 'FAIL':
        problems.append('设计待办记录自相矛盾（design-closure 审核 FAIL）：' +
                        '；'.join('%s %s' % (e.get('code'), e.get('item')) for e in (audit.get('errors') or [])[:5]))
    if visual and visual.get('status') not in VISUAL:
        problems.append('visual-review.json 的 status 必须是 %s 之一' % '/'.join(VISUAL))
    lessons, events = {}, None
    if data['lessons.json'] is not None:
        lesson_problems, events = check_lessons(data['lessons.json'])
        problems += lesson_problems
        lessons = data['lessons.json']
    if data['page-plan.json'] is not None:
        problems += check_page_plan(data['page-plan.json'], intent, visual, lessons)
    problems += check_visual_items(root, visual)
    selection = data['selection.json'] or {}
    if data['selection.json'] is not None:
        problems += check_selection(selection, intent, root)
    if responses is not None:
        problems += check_responses(responses, work, intent, closure, root, events)
    problems += check_language(closure, notes)
    for i, h in enumerate(notes.get('highlights') or []):
        if text(h) and any(w in h for w in PROCESS_WORDS):
            problems.append('关键设计依据第 %d 条写的是审查流程，不是设计依据：“%s”' % (i + 1, h.strip()[:40]))

    gates = summary.get('gates') or {}
    shown = [(key, label, (gates.get(key) or {}).get('status')) for key, label in GATES.items() if key in gates]
    gate_counts = Counter(status for _, _, status in shown)
    # Drawing gates are ASG's own work: a failed one is redrawn, never delivered.
    # Listing it as a problem also makes pack_design.py refuse the delivery.
    for key, label, status in shown:
        if key in ('readability', 'geometry') and status == 'FAIL':
            problems.append('“%s”没通过：这是画图问题，改图到 PASS 再重新验证后才能交付' % label)
    open_work = [w for w in work.values() if w.get('status') == 'open']
    handoffs = [w for w in work.values() if w.get('status') == 'handoff']
    req_counts = Counter(r.get('status') for r in requirements)
    items = (responses or {}).get('items') or []
    reply_counts = Counter(i.get('response') for i in items if isinstance(i, dict))

    out = ['# %s' % (title or '原理图设计报告'), '']
    if problems:
        out += ['> **设计记录本身有问题，下面的结论不可靠。** 先改正记录再重新生成报告：' +
                '；'.join(cell(p) for p in problems[:6]), '']
    out += ['## 结论', '']
    parts = len(intent.get('components') or [])
    sheets = len(summary.get('sheets') or [])
    out.append('- **规模**：器件 %d 个，图纸 %d 页。' % (parts, sheets))
    out.append('- **自动检查**：共 %d 项。%s。' % (len(shown), '，'.join(
        '%s %d 项' % (label, gate_counts.get(key, 0)) for key, label in GATE_RESULTS.items()
        if key != 'CONDITIONAL' or gate_counts.get(key))))
    out.append('- **看图检查**：%s。' % VISUAL.get(visual.get('status'), '没有记录'))
    out.append('- **需求**：共 %d 条。%s。' % (len(requirements), '，'.join(
        '%s %d 条' % (label, req_counts.get(key, 0)) for key, label in REQUIREMENTS.items())))
    if items:
        out.append('- **收到的审查意见**：%d 条。%s。' % (len(items), '，'.join(
            '%s %d 条' % (label, reply_counts[key]) for key, (label, _) in RESPONSES.items() if reply_counts.get(key))))
    missing = []
    failed = [label for _, label, status in shown if status == 'FAIL']
    short = [label for _, label, status in shown if status not in ('PASS', 'FAIL', 'CONDITIONAL')]
    if failed:
        missing.append('%d 项自动检查没通过：%s' % (len(failed), '、'.join(failed)))
    if short:
        missing.append('%d 项自动检查资料不足或没做：%s' % (len(short), '、'.join(short)))
    if visual.get('status') != 'REVIEWED':
        missing.append('看图检查%s' % VISUAL.get(visual.get('status'), '没有记录'))
    by_stage = Counter(w.get('stage') for w in open_work)
    if open_work:
        missing.append('%d 件待办没做完（%s）' % (len(open_work), '，'.join(
            '%s %d 件' % (STAGES[s], by_stage[s]) for s in STAGES if by_stage.get(s))))
    if problems:
        missing.append('设计记录有问题，见开头')
    if missing:
        out.append('- **设计是否完成**：还没完成。还差：')
        out += ['  %d. %s；' % (i, m) for i, m in enumerate(missing, 1)]
        out[-1] = out[-1][:-1] + '。'
    else:
        out.append('- **设计是否完成**：已完成。自动检查、看图检查和设计待办都已处理完。')
    asks = [w for w in open_work if w.get('stage') == 'requirement']
    if asks:
        out.append('- **请你定的需求**：%d 件（%s）。本版先按写明的假设设计，定下来后可能要改图，列在“待办”最前面。'
                   % (len(asks), '、'.join(w['id'] for w in asks)))
    if open_work:
        out.append('- **待办**：%d 件，%s按可能后果从重到轻列在“待办”一节。'
                   % (len(open_work), '等你定的需求排最前，其余' if asks else ''))
    out.append('- 这份报告只说明 ASG 自己的设计和自检做到哪一步，不代替独立审查。')
    out.append('')
    if notes.get('summary'):
        out += [notes['summary'], '']
    if items:
        redrawn = reply_counts.get('REDESIGN', 0) + reply_counts.get('CALC_DOC', 0)
        out += ['本版收到 %d 条审查意见：改图或补计算/补文档 %d 条，其余 %d 条登记为待办、交给后续环节或不采纳。'
                % (len(items), redrawn, len(items) - redrawn), '']

    roles = [r for r in selection.get('roles') or [] if isinstance(r, dict)]
    if roles:
        out += ['## 核心器件选型', '', '| 角色 | 位号 | 选定 | 候选数 | 理由 | 淘汰依据 |', '|---|---|---|---|---|---|']
        for r in roles:
            chosen = [c for c in r.get('candidates') or [] if isinstance(c, dict) and c.get('status') == 'selected']
            out.append('| %s | %s | %s | %d | %s | %s |' % (
                cell(r.get('role', '')), '、'.join(r.get('refs') or []),
                cell(chosen[0].get('mpn', '')) if chosen else '未选定', len(r.get('candidates') or []),
                cell(chosen[0].get('reason', '')) if chosen else cell(r.get('single_candidate_reason', '')),
                cell('；'.join(r.get('_basis') or []))))
        out.append('')

    if notes.get('changes') or change:
        out += ['## 这版改了什么', '']
        if change:
            out += ['器件数：%s → %s。' % (change.get('old_components', '?'), change.get('new_components', '?')), '']
        if notes.get('changes'):
            out += [notes['changes'], '']

    if items:
        out += ['## 审查意见怎么处理的', '', '| 编号 | 意见 | 处理 | 说明 |', '|---|---|---|---|']
        for i in items:
            label = RESPONSES.get(i.get('response'), ('?',))[0]
            out.append('| %s | %s | %s | %s |' % (cell(i.get('id', '')), cell(i.get('comment', '')), label,
                                                   cell(i.get('detail', ''))))
        out.append('')

    events_list = [e for e in (lessons.get('events') or []) if isinstance(e, dict)]
    if events_list:
        out += ['## 本版学到的东西', '', '| 来源 | 归因 | 改了什么 |', '|---|---|---|']
        for e in events_list:
            out.append('| %s | %s | %s |' % (cell(e.get('source', '')), CAUSE_WORDS.get(e.get('cause'), cell(e.get('cause', ''))),
                                            cell(e.get('change') or e.get('why_none') or '')))
        out.append('')

    if open_work:
        out += ['## 待办', '', SEVERITY_LEGEND, '']
        order = lambda w: (w.get('stage') != 'requirement', SEVERITIES.index(w['severity']) if w.get('severity') in SEVERITIES else len(SEVERITIES),
                           -len(w.get('requirements') or []))
        item_notes = notes.get('items') or {}
        for w in sorted(open_work, key=order):
            level = w.get('severity')
            out += ['### %s（%s）' % (w['id'], ('%s：%s' % (level, SEVERITY_WORDS[level])) if level in SEVERITY_WORDS else '未定后果'), '']
            if item_notes.get(w['id']):
                out += [item_notes[w['id']], '']
            for label, value in (('类型', STAGES.get(w.get('stage'), w.get('stage'))),
                                 ('本版按什么假设设计', w.get('assumption')), ('要做什么', w.get('action')),
                                 ('找谁', w.get('owner')), ('拿不到时的替代做法', w.get('fallback')),
                                 ('要先完成', '、'.join(w.get('blocked_by') or [])),
                                 ('影响的需求', '、'.join(w.get('requirements') or []))):
                if text(value):
                    out.append('- **%s**：%s' % (label, value))
            out.append('')

    if handoffs:
        out += ['## 交给后续环节的要求', '',
                '下面这些要在 PCB、结构、样机测试等后续环节落实，不是原理图没做完。原理图交出时把这张表一起交给对应负责方。', '',
                '| 负责方 | 环节 | 要落实的要求 |', '|---|---|---|']
        for w in handoffs:
            out.append('| %s | %s | %s |' % (cell(w.get('owner') or '未指定'), STAGES.get(w.get('stage'), ''),
                                            cell(w.get('action') or '')))
        out.append('')

    conditional = [c for c in calculations if c.get('conclusion') == 'conditional']
    if conditional:
        out += ['## 有条件成立的计算', '',
                '这些计算按设计用途已经够用，不阻塞出图；结论建立在下面写明的假设或没算进去的项上，'
                '按最坏情况逐条证明留给独立审查。', '',
                '| 计算 | 涉及的需求 | 算出的值与门槛 | 假设或没算进去的项 |', '|---|---|---|---|']
        for c in conditional:
            out.append('| %s | %s | %s | %s |' % (c.get('id'), '、'.join(c.get('requirements') or []),
                                            cell('；'.join(check_text(k) for k in c.get('checks') or [])),
                                            cell('；'.join((c.get('assumptions') or []) + (c.get('omitted_terms') or [])))))
        out.append('')

    if shown:
        out += ['## 自动检查明细', '', '| 检查 | 结果 |', '|---|---|']
        for key, label, status in shown:
            detail = gates[key]
            extra = '，'.join('%s %s' % (k, v) for k, v in detail.items() if k in ('violations', 'errors') and v)
            if key == 'geometry':
                gaps = sum(len(v) for v in (detail.get('coverage_gaps') or {}).values())
                pins = sum(len(v) for v in (detail.get('render_review_items') or {}).values())
                extra = '，'.join(x for x in (extra, '没覆盖的对象 %d 项' % gaps if gaps else '',
                                              '%d 个引脚文字交看图检查' % pins if pins else '') if x)
            out.append('| %s | %s%s |' % (label, GATE_RESULTS.get(status, status), ('（%s）' % extra) if extra else ''))
        out.append('')

    docs = sorted(p.relative_to(root).as_posix() for p in (root / '设计资料').rglob('*') if p.is_file()) \
        if (root / '设计资料').is_dir() else []
    if docs:
        out += ['## 设计资料', ''] + ['- [%s](%s)' % (Path(d).stem, d) for d in docs] + ['']
    if notes.get('highlights'):
        out += ['## 关键设计依据', ''] + ['- ' + h for h in notes['highlights'][:8]] + ['']

    cov = Counter(c.get('coverage') for c in calculations)
    con = Counter(c.get('conclusion') for c in calculations)
    stage_status = Counter((w.get('stage'), w.get('status')) for w in work.values())
    out += ['## 数字一览', '', '| 项目 | 数量 |', '|---|---|',
            '| 器件 / 图纸页数 | %d / %d |' % (parts, sheets),
            '| 需求：%s | %s |' % (' / '.join(REQUIREMENTS.values()), ' / '.join(str(req_counts.get(k, 0)) for k in REQUIREMENTS)),
            '| 计算：上下界完整 / 只算了一部分 | %d / %d |' % (cov.get('bounded', 0), cov.get('partial', 0)),
            '| 计算结论：满足 / 有条件满足 / 不满足 | %d / %d / %d |' % (con.get('supported', 0), con.get('conditional', 0), con.get('failed', 0)),
            '| 待办：设计没做完 / 缺外部资料（未关闭） | %d / %d |' % (stage_status.get(('design', 'open'), 0), stage_status.get(('external', 'open'), 0)),
        ] + (['| 待办：等用户定需求（未关闭） | %d |' % stage_status[('requirement', 'open')]]
             if stage_status.get(('requirement', 'open')) else []) + [
            '| 交给后续环节的要求 | %d |' % len(handoffs),
            '| 已关闭的待办 | %d |' % sum(v for (s, st), v in stage_status.items() if st == 'closed'), '']
    out += ['## 详细记录', '',
            '原理图在 `原理图/`（KiCad 工程、PDF、网表、BOM）。`record/` 里是生成这份报告用的记录：'
            '`electrical-intent.json` 是设计要求表，`design-closure.json` 是需求、待办和计算的处理情况，'
            '`summary.json` 是自动检查结果，`visual-review.json` 是看图检查，`manifest.json` 记录用到的需求、'
            '原厂资料和前一版设计的位置与校验码。', '']
    return '\n'.join(out), problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('delivery', help='delivery folder holding record/')
    parser.add_argument('--notes', help='notes.json written by the agent')
    parser.add_argument('--title')
    args = parser.parse_args(argv)
    notes = json.loads(Path(args.notes).read_text(encoding='utf-8')) if args.notes else None
    report, problems = render(args.delivery, notes, args.title)
    target = Path(args.delivery) / REPORT
    target.write_text(report + '\n', encoding='utf-8')
    print('wrote', target)
    for p in problems:
        print('PROBLEM:', p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
