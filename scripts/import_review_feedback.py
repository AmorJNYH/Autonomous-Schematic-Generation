#!/usr/bin/env python3
"""Map one schematic-review (SR) result set to ASG next actions.

This is routing, not design approval: it reads SR's own gap_cause / stage records and
never re-judges a check. Every agent gets the same action list for the same SR files.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

STAGE_NA = 'OUTSIDE_SCHEMATIC_STAGE'
# SR record -> (ASG action, design-closure work stage, controller open_items kind).
# See references/review-feedback.md for what each action means.
ROUTES = {
    'FAIL': ('REDESIGN', 'design', 'DESIGN'),
    'DESIGN_OPEN': ('DESIGN', 'design', 'DESIGN'),
    'EXTERNAL_DATA': ('OBTAIN_EVIDENCE', 'external', 'EVIDENCE'),
    'REQUIREMENT_OPEN': ('ASK_REQUIREMENT_OWNER', None, 'REQUIREMENT'),
    'REVIEW_INCOMPLETE': ('WAIT_FOR_SR', None, 'REVIEW'),
    'USER_DEFERRED': ('NONE', None, None),
    STAGE_NA: ('HANDOFF', 'validation', 'DOWNSTREAM'),
}
HISTORY_RULE = 'REQ-H02'  # prior-round dispositions; SR counts them apart


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route(row):
    result = row.get('review_result')
    if result == 'FAIL':
        return 'FAIL'
    if result == 'INSUFFICIENT':
        return row.get('gap_cause') or 'UNSPECIFIED'
    if result == 'NA' and row.get('na_reason') == STAGE_NA:
        return STAGE_NA
    return None


def import_feedback(results, gate):
    errors = []
    if gate.get('valid') is not True:
        errors.append('SR gate is not valid; return the records to SR before acting on them')
    checks = results.get('checks') if isinstance(results.get('checks'), list) else []
    tasks = ((gate.get('workflow') or {}).get('work_items') or [])
    task_of = {}
    for task in tasks:
        for cid in task.get('check_ids') or []:
            task_of.setdefault(cid, []).append(task)
    actions = []
    for row in checks:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        cid = row['id']
        if cid.split('.', 1)[0] == HISTORY_RULE:
            continue
        key = route(row)
        if key is None:
            continue
        if key not in ROUTES:
            errors.append(cid + ': unrouted SR record ' + repr(key) + '; rerun the current SR so every gap has a gap_cause')
            continue
        action, stage, kind = ROUTES[key]
        item = {'check_id': cid, 'sr_route': key, 'action': action,
                'closure_stage': stage, 'open_item_kind': kind,
                'sr_work_items': sorted(t['id'] for t in task_of.get(cid, []) if isinstance(t.get('id'), str))}
        if row.get('finding_id'):
            item['finding_id'] = row['finding_id']
        if isinstance(row.get('input_requests'), dict):
            item['input_requests'] = row['input_requests']
        if key == STAGE_NA:
            item['handoff'] = row.get('handoff')
        options = [t['design_option'] for t in task_of.get(cid, []) if isinstance(t.get('design_option'), dict)]
        proposed = [o for o in options if o.get('status') == 'PROPOSED']
        if proposed:
            # A proposal is a candidate only; ASG adopts it after its own convergence estimate.
            item['sr_design_options'] = proposed
        actions.append(item)
    counts = {}
    for item in actions:
        counts[item['action']] = counts.get(item['action'], 0) + 1
    summary = gate.get('categorized_summary') or {}
    metrics = {
        # Convergence is judged on these SR numbers, round over round (references/review-feedback.md).
        'unique_findings': summary.get('unique_findings'),
        'unique_work_items': summary.get('unique_work_items'),
        'design_actions': counts.get('REDESIGN', 0) + counts.get('DESIGN', 0),
        'evidence_actions': counts.get('OBTAIN_EVIDENCE', 0),
    }
    return {'schema_version': 1, 'status': 'FAIL' if errors else 'PASS', 'errors': errors,
            'sr_release': gate.get('release'), 'metrics': metrics,
            'action_counts': dict(sorted(counts.items())), 'actions': actions,
            'scope': 'Routing of SR records only; does not verify SR conclusions or approve a design change.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', help='SR review-results.json')
    parser.add_argument('gate', help='SR review-gate.json from the same run')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    out = import_feedback(json.loads(Path(args.results).read_text()), json.loads(Path(args.gate).read_text()))
    out['sources'] = {'results_sha256': digest(args.results), 'gate_sha256': digest(args.gate)}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(out['status'], json.dumps(out['action_counts'], ensure_ascii=False))
    return 0 if out['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
