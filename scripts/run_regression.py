#!/usr/bin/env python3
"""Re-run the report and packing checks on real deliveries and compare with a baseline.

Protects every board drawn so far from a rule change made for the next one:
a board whose report problems, packing errors or gate statuses get worse
fails the run. Boards live outside the skill (tests/regression/boards.json);
a missing folder is skipped, not failed. Nothing in a delivery is written.

  run_regression.py                      # compare with tests/regression/baseline.json
  run_regression.py --update-baseline    # accept the current numbers
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pack_design import check  # noqa: E402
from render_design_report import GATES, render  # noqa: E402

REG = HERE.parent / 'tests' / 'regression'
GATE_RANK = {'PASS': 0, 'CONDITIONAL': 1, 'FAIL': 3}


def rank(status):
    return GATE_RANK.get(status, 2)


def measure(board):
    root = Path(board['path']).expanduser()
    if not (root / 'record').is_dir():
        return {'status': 'SKIPPED', 'reason': 'not on this machine: %s' % root}
    notes_path = root / 'record' / 'notes.json'
    notes = json.loads(notes_path.read_text(encoding='utf-8')) if notes_path.is_file() else None
    _, problems = render(root, notes, board.get('title'))
    summary_path = root / 'record' / 'summary.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8')) if summary_path.is_file() else {}
    gates = {k: (summary.get('gates') or {}).get(k, {}).get('status') for k in GATES if k in (summary.get('gates') or {})}
    closure_path = root / 'record' / 'design-closure.json'
    closure = json.loads(closure_path.read_text(encoding='utf-8')) if closure_path.is_file() else {}
    open_work = sum(1 for w in closure.get('work_items') or [] if isinstance(w, dict) and w.get('status') == 'open')
    pack_errors = check(root)
    return {'status': 'MEASURED', 'report_problems': len(problems), 'pack_errors': len(pack_errors),
            'gates': gates, 'open_work': open_work, 'problems': problems, 'pack_error_lines': pack_errors}


def compare(current, base):
    reasons = []
    for key, label in (('report_problems', 'report problems'), ('pack_errors', 'packing errors')):
        if current[key] > base.get(key, 0):
            reasons.append('%s %d -> %d' % (label, base.get(key, 0), current[key]))
    for gate, status in current['gates'].items():
        before = (base.get('gates') or {}).get(gate)
        if before is not None and rank(status) > rank(before):
            reasons.append('gate %s %s -> %s' % (gate, before, status))
    return reasons


def run(boards_path=REG / 'boards.json', baseline_path=REG / 'baseline.json', update=False):
    boards = json.loads(Path(boards_path).read_text(encoding='utf-8'))['boards']
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8')) if Path(baseline_path).is_file() else {'boards': {}}
    results, new_base, overall = {}, {}, 'PASS'
    for board in boards:
        m = measure(board)
        if m['status'] == 'SKIPPED':
            results[board['id']] = m
            if board['id'] in baseline['boards']:
                new_base[board['id']] = baseline['boards'][board['id']]
            continue
        slim = {k: m[k] for k in ('report_problems', 'pack_errors', 'gates', 'open_work')}
        base = baseline['boards'].get(board['id'])
        if base is None:
            m['status'], m['reasons'] = 'NEW', ['no baseline yet; run with --update-baseline']
        else:
            reasons = compare(slim, base)
            m['status'], m['reasons'] = ('FAIL' if reasons else 'PASS'), reasons
            if not reasons and (slim['report_problems'] < base.get('report_problems', 0) or slim['pack_errors'] < base.get('pack_errors', 0)):
                m['reasons'] = ['improved; run with --update-baseline to lower the bar']
        if m['status'] == 'FAIL' or (m['status'] == 'NEW' and overall != 'FAIL'):
            overall = m['status'] if m['status'] == 'FAIL' else 'NEW'
        results[board['id']] = m
        new_base[board['id']] = slim
    if update:
        Path(baseline_path).write_text(json.dumps({'generated': date.today().isoformat(), 'boards': new_base},
                                                  ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        overall = 'UPDATED'
    return {'status': overall, 'boards': results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--boards', type=Path, default=REG / 'boards.json')
    ap.add_argument('--baseline', type=Path, default=REG / 'baseline.json')
    ap.add_argument('--update-baseline', action='store_true')
    ap.add_argument('--verbose', action='store_true', help='print every problem line')
    args = ap.parse_args(argv)
    report = run(args.boards, args.baseline, args.update_baseline)
    for board_id, m in report['boards'].items():
        line = '%-14s %s' % (board_id, m['status'])
        if m['status'] != 'SKIPPED':
            line += '  problems %d, pack errors %d, gates %s' % (m['report_problems'], m['pack_errors'], ','.join(
                '%s=%s' % (k, v) for k, v in m['gates'].items()))
        print(line)
        for r in m.get('reasons') or ([m['reason']] if m.get('reason') else []):
            print('    ' + r)
        if args.verbose:
            for p in m.get('problems') or []:
                print('    report: ' + p)
            for p in m.get('pack_error_lines') or []:
                print('    pack: ' + p)
    print(report['status'])
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
