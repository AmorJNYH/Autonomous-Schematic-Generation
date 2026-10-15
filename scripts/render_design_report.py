#!/usr/bin/env python3
"""Write 设计报告.md for one delivery folder from its own records.

Every number and status comes from <delivery>/record/; the agent adds plain-language
text only through notes.json {summary, changes, items{work_id: text}, highlights[≤8]}.
Records that are missing or inconsistent are reported at the top instead of guessed.
"""
import argparse
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

REPORT = '设计报告.md'
SEVERITIES = ('P0', 'P1', 'P2', 'P3')
SEVERITY_WORDS = {'P0': '可能损坏器件或危及安全', 'P1': '必需功能可能不达标',
                  'P2': '局部或次要问题', 'P3': '可选优化'}
SEVERITY_LEGEND = '可能后果：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。'
GATES = OrderedDict([
    ('erc', 'KiCad 电气规则检查（ERC）'),
    ('intent_netlist', '网表与设计要求表逐脚对照'),
    ('hierarchy', '图纸层次与页数'),
    ('symbol_integrity', '符号引脚完整'),
    ('readability', '图面可读性'),
    ('geometry', '图面几何（重叠、穿线）'),
    ('external_supply', '外部供电声明'),
    ('reference_contract', '外围电路按手册核对'),
    ('design_change', '改动与预期一致'),
])
GATE_RESULTS = OrderedDict([('PASS', '通过（PASS）'), ('FAIL', '没通过（FAIL）'),
                            ('INSUFFICIENT', '资料不足（INSUFFICIENT）'), ('CONDITIONAL', '有条件通过')])
VISUAL = {'REVIEWED': '已完成', 'REVIEW_PENDING': '还没做完', 'REWORK_REQUIRED': '发现要返工的地方'}
STAGES = {'design': '设计没做完', 'external': '缺外部资料', 'validation': '样机或试验验证', 'pcb': 'PCB 实现'}
REQUIREMENTS = OrderedDict([('design_supported', '有设计依据'), ('conditional', '有条件成立'), ('open', '还没有设计')])
RESPONSES = OrderedDict([
    ('REDESIGN', ('改图', 'changes')), ('DESIGN', ('补设计', 'work_items')),
    ('OBTAIN_DATA', ('补资料', 'work_items')), ('ASK_USER', ('请用户定需求', 'detail')),
    ('HANDOFF', ('交给后续环节', 'work_items')), ('DECLINE', ('不采纳', 'evidence')),
    ('DEFERRED', ('已暂缓', 'detail'))])
RESPONSE_STAGE = {'DESIGN': ('design',), 'OBTAIN_DATA': ('external',), 'HANDOFF': ('validation', 'pcb')}
REQUIRED = ('electrical-intent.json', 'design-closure.json', 'design-closure-audit.json',
            'summary.json', 'visual-review.json')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').strip()


def load(path):
    try:
        return json.loads(path.read_text(encoding='utf-8')), None
    except FileNotFoundError:
        return None, '缺少 record/%s' % path.name
    except (OSError, ValueError) as error:
        return None, 'record/%s 读不出来：%s' % (path.name, error)


def check_responses(data, work):
    """Each review comment has one allowed response and what that response requires."""
    errors = []
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        return ['review-responses.json 必须是 schema_version 1 的对象']
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
        field = RESPONSES[response][1]
        if field != 'detail' and not (isinstance(item.get(field), list) and item[field]):
            errors.append('%s：处理方式为“%s”时必须填 %s' % (key, RESPONSES[response][0], field))
        for wid in item.get('work_items') or []:
            row = work.get(wid)
            if row is None:
                errors.append('%s：引用的待办 %s 不在 design-closure.json 里' % (key, wid))
            elif response in RESPONSE_STAGE and row.get('stage') not in RESPONSE_STAGE[response]:
                errors.append('%s：待办 %s 的阶段与处理方式“%s”不符' % (key, wid, RESPONSES[response][0]))
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
    if responses is not None:
        problems += check_responses(responses, work)

    gates = summary.get('gates') or {}
    shown = [(key, label, (gates.get(key) or {}).get('status')) for key, label in GATES.items() if key in gates]
    gate_counts = Counter(status for _, _, status in shown)
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
    if open_work:
        out.append('- **待办**：%d 件，按可能后果从重到轻列在“待办”一节。' % len(open_work))
    out.append('- 这份报告只说明 ASG 自己的设计和自检做到哪一步，不代替独立审查。')
    out.append('')
    if notes.get('summary'):
        out += [notes['summary'], '']

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

    if open_work:
        out += ['## 待办', '', SEVERITY_LEGEND, '']
        order = lambda w: (SEVERITIES.index(w['severity']) if w.get('severity') in SEVERITIES else len(SEVERITIES),
                           -len(w.get('requirements') or []))
        item_notes = notes.get('items') or {}
        for w in sorted(open_work, key=order):
            level = w.get('severity')
            out += ['### %s（%s）' % (w['id'], ('%s：%s' % (level, SEVERITY_WORDS[level])) if level in SEVERITY_WORDS else '未定后果'), '']
            if item_notes.get(w['id']):
                out += [item_notes[w['id']], '']
            for label, value in (('类型', STAGES.get(w.get('stage'), w.get('stage'))), ('要做什么', w.get('action')),
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

    if shown:
        out += ['## 自动检查明细', '', '| 检查 | 结果 |', '|---|---|']
        for key, label, status in shown:
            detail = gates[key]
            extra = '，'.join('%s %s' % (k, v) for k, v in detail.items() if k in ('violations', 'errors') and v)
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
