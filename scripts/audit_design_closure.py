#!/usr/bin/env python3
"""Audit evidence-bound design claims, not electrical physics or certification.

A record can be consistent yet INCOMPLETE. PASS means its declared design work
is closed; native checks and visual review remain separate.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from design_frontier import frontier


SEVERITIES = ('P0', 'P1', 'P2', 'P3')
OPERATORS = {'<=': lambda v, l: v <= l, '<': lambda v, l: v < l,
             '>=': lambda v, l: v >= l, '>': lambda v, l: v > l}
# Parts whose job is to set or clamp a voltage. Each one needs a calculation
# naming it, so a protection threshold cannot ship as prose only.
THRESHOLD_PART = re.compile(r'zener|tvs|tl431|atl431|lm4040|shunt.?ref|voltage.?ref|^power:vref', re.I)
WINDOW_SIDES = ('no_false_trip', 'protection')
# Where each number in a calculation comes from (parameter_version 1). A device
# parameter cites the datasheet page it was read from; one the datasheet does
# not give is "unspecified" and ties to a recorded operating-point decision.
PARAMETER_BASES = ('guaranteed', 'typical', 'derived', 'design_choice', 'model', 'unspecified')
DATASHEET = re.compile(r'^datasheet:.+#p\d+$')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def audit_operating_points(record, work, refs, error, need):
    """Pin operating modes: one the datasheet does not specify needs every specified alternative ruled out."""
    points = {}
    rows = record.get('operating_points', [])
    if not isinstance(rows, list):
        error('schema', 'operating_points must be a list')
        return points
    for row in rows:
        if not isinstance(row, dict) or not text(row.get('id')):
            error('schema', 'operating_points entry requires a nonempty string id')
            continue
        key = row['id']
        if key in points:
            error('duplicate_id', 'operating_points:' + key)
        points[key] = row
        if not isinstance(row.get('refs'), list) or not row['refs'] or any(r not in refs for r in row['refs']):
            error('operating_point_refs', key)
        if not isinstance(row.get('pins'), list) or not row['pins'] or not all(text(p) for p in row['pins']):
            error('schema', key + ':pins must be a nonempty string list')
        if not text(row.get('mode')) or not isinstance(row.get('specified'), bool):
            error('schema', key + ':needs mode and specified (true/false)')
            continue
        # specified: where the datasheet specifies this mode; otherwise where it was looked for and is absent.
        if not (isinstance(row.get('source'), str) and DATASHEET.match(row['source']) and text(row.get('locator'))):
            error('operating_point_source', key)
        if row['specified']:
            continue
        alternatives = row.get('alternatives')
        if not isinstance(alternatives, list) or not alternatives:
            error('unspecified_operation_without_alternatives', key)
            alternatives = []
        for i, alt in enumerate(alternatives):
            if (not isinstance(alt, dict) or not text(alt.get('approach')) or not text(alt.get('reason'))
                    or not isinstance(alt.get('specified'), bool) or not isinstance(alt.get('feasible'), bool)):
                error('schema', key + ':alternatives[%d] needs approach, specified, feasible and reason' % i)
            elif alt['specified'] and alt['feasible']:
                error('unspecified_operation_with_specified_alternative', key + ':' + alt['approach'])
        item = work.get(row.get('work_item'))
        if not item or item.get('stage') != 'external':
            error('unspecified_operation_without_vendor_item', key)
        need('unspecified_operation', key)
    return points


def audit_parameters(key, row, refs, points, calculations, error):
    params = row.get('parameters')
    if not isinstance(params, list) or not params:
        error('missing_parameters', key)
        return
    for i, p in enumerate(params):
        where = key + ':parameters[%d]' % i
        if not isinstance(p, dict) or not text(p.get('name')) or not isinstance(p.get('unit'), str):
            error('schema', where + ' needs name and unit')
            continue
        where = key + ':' + p['name']
        basis = p.get('basis')
        if basis not in PARAMETER_BASES:
            error('schema', where + ':basis must be one of ' + '/'.join(PARAMETER_BASES))
            continue
        if basis != 'unspecified' and not finite(p.get('value')):
            error('schema', where + ':value must be a finite number')
        if basis in ('guaranteed', 'typical', 'design_choice', 'unspecified') and p.get('ref') not in refs:
            error('parameter_ref', where)
        cited = isinstance(p.get('source'), str) and DATASHEET.match(p['source']) and text(p.get('locator'))
        if basis in ('guaranteed', 'typical', 'unspecified') and not cited:
            error('parameter_without_datasheet_location', where)
        if basis == 'derived':
            source = p.get('source')
            if not text(p.get('derivation')) or not (
                    (isinstance(source, str) and DATASHEET.match(source)) or
                    (isinstance(source, str) and source.startswith('calc:') and source[5:] in calculations)):
                error('derived_parameter_without_basis', where)
        if basis == 'model' and not text(p.get('reason')):
            error('model_parameter_without_reason', where)
        if basis == 'unspecified':
            point = points.get(p.get('operating_point'))
            if not point or point.get('specified') is not False:
                error('unspecified_parameter_without_operating_point', where)
        if basis in ('typical', 'unspecified') and row.get('conclusion') == 'supported':
            error('supported_with_unguaranteed_parameter', where)


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(p, root, inputs):
    """Evidence lives under the artifact root, or in a declared input (requirements, datasheets)."""
    path = (root / p).resolve()
    if path.is_relative_to(root) and path.is_file():
        return path
    for base in inputs or ():
        base = Path(base).resolve()
        for candidate in ((base / p, base / Path(p).name) if base.is_dir() else (base,)):
            if candidate.is_file() and candidate.name == Path(p).name:
                return candidate
    return None


def audit(record, intent_path, artifact_root, inputs=None):
    errors, pending = [], []
    def error(code, item):
        errors.append({'code': code, 'item': str(item)})
    def need(code, item):
        pending.append({'code': code, 'item': str(item)})
    if not isinstance(record, dict):
        return {'status': 'FAIL', 'errors': [{'code': 'schema', 'item': 'record must be an object'}], 'pending': []}
    if record.get('schema_version') != 1:
        error('schema', 'schema_version must be 1')
    if record.get('intent_sha256') != sha256(intent_path):
        error('stale_intent', intent_path.name)
    intent = json.loads(intent_path.read_text(encoding='utf-8'))
    refs = {c['ref'] for c in intent['components']}
    threshold_parts = sorted(c['ref'] for c in intent['components']
                             if THRESHOLD_PART.search(str(c.get('lib_id', ''))))
    root = artifact_root.resolve()
    tables = {}
    for key in ('evidence', 'requirements', 'work_items', 'calculations'):
        entries = record.get(key)
        table = {}
        if not isinstance(entries, list):
            error('schema', key + ' must be a list')
            entries = []
        for row in entries:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                error('schema', key + ' entry requires a nonempty string id')
                continue
            if row['id'] in table:
                error('duplicate_id', key + ':' + row['id'])
            table[row['id']] = row
        tables[key] = table
    evidence, requirements, work, calculations = (tables[k] for k in ('evidence', 'requirements', 'work_items', 'calculations'))
    if not requirements:
        need('missing_requirements', 'No requirements reviewed')
    for key, row in evidence.items():
        p = row.get('path')
        if not isinstance(p, str) or not p or Path(p).is_absolute():
            error('evidence_path', key)
            continue
        path = resolve(p, root, inputs)
        if path is None:
            error('evidence_missing_or_outside_root', key)
        elif row.get('sha256') != sha256(path):
            error('stale_evidence', key)
        if not isinstance(row.get('locator'), str) or not row['locator'].strip():
            error('missing_locator', key)

    def linked(row, field, table, required=False):
        values = row.get(field)
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            error('schema', row['id'] + ':' + field + ' must be a string list')
            return []
        if required and not values:
            error('missing_' + field, row['id'])
        for key in values:
            if key not in table:
                error('unknown_' + field, row['id'] + ':' + key)
        return values

    for key, row in work.items():
        affected = linked(row, 'requirements', requirements, True)
        linked(row, 'evidence', evidence, row.get('status') == 'closed')
        stage, state = row.get('stage'), row.get('status')
        if stage not in ('requirement', 'design', 'external', 'validation', 'pcb') or state not in ('open', 'closed', 'handoff'):
            error('schema', key + ':invalid stage/status')
        if state == 'handoff' and stage not in ('validation', 'pcb'):
            error('unfinished_design_handoff', key)
        if state != 'closed':
            for field in ('action', 'owner'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    error('missing_' + field, key)
            if stage in ('validation', 'pcb') and state == 'handoff':
                linked(row, 'evidence', evidence, True)
            else:
                need('open_' + str(stage), key)
                # Possible consequence if left undone; orders the report's to-do list.
                if row.get('severity') not in SEVERITIES:
                    error('missing_severity', key)
        if stage == 'pcb':
            if row.get('scope') not in ('footprint_library', 'layout_implementation', 'dfm'):
                error('pcb_scope', key)
            prerequisites = linked(row, 'electrical_preconditions', work, True)
            for dep in prerequisites:
                item = work.get(dep, {})
                if item.get('stage') != 'design' or item.get('status') != 'closed':
                    error('pcb_electrical_precondition', key + ':' + dep)
        if stage == 'external' and state != 'closed' and not row.get('fallback'):
            error('missing_fallback_assessment', key)
        # A requirement gap still waiting on the user must say what this version assumed.
        if stage == 'requirement' and state != 'closed' and not (
                isinstance(row.get('assumption'), str) and row['assumption'].strip()):
            error('missing_assumption', key)
        for rid in affected:
            if rid in requirements and key not in requirements[rid].get('depends_on', []):
                error('unlinked_dependency', rid + ':' + key)

    for key, row in requirements.items():
        state = row.get('status')
        if state not in ('design_supported', 'conditional', 'open'):
            error('schema', key + ':invalid requirement status')
        linked(row, 'evidence', evidence, True)
        linked(row, 'refs', refs)
        deps = linked(row, 'depends_on', work)
        if not isinstance(row.get('implementation'), str) or not row['implementation'].strip():
            error('missing_implementation', key)
        if state != 'design_supported':
            need('requirement_not_supported', key)
        for dep in deps:
            item = work.get(dep, {})
            closed = item.get('status') == 'closed' or (item.get('stage') in ('validation', 'pcb') and item.get('status') == 'handoff')
            if state == 'design_supported' and not closed:
                error('unsupported_requirement_claim', key + ':' + dep)

    parameters = 'parameter_version' in record
    if parameters and record['parameter_version'] != 1:
        error('schema', 'parameter_version must be 1')
        parameters = False
    points = audit_operating_points(record, work, refs, error, need) if parameters else {}
    for key, row in calculations.items():
        if parameters:
            audit_parameters(key, row, refs, points, calculations, error)
        linked(row, 'requirements', requirements, True)
        linked(row, 'evidence', evidence, True)
        coverage, conclusion = row.get('coverage'), row.get('conclusion')
        if coverage not in ('bounded', 'partial') or conclusion not in ('supported', 'conditional', 'failed'):
            error('schema', key + ':invalid coverage/conclusion')
        omitted = row.get('omitted_terms')
        if not isinstance(omitted, list) or any(not isinstance(x, str) for x in omitted):
            error('schema', key + ':omitted_terms must be a string list')
            omitted = []
        if coverage == 'bounded' and omitted:
            error('contradictory_coverage', key)
        if conclusion == 'supported' and (coverage != 'bounded' or omitted):
            error('partial_calculation_claimed_supported', key)
        assumptions = row.get('assumptions', [])
        if not isinstance(assumptions, list) or any(not isinstance(x, str) for x in assumptions):
            error('schema', key + ':assumptions must be a string list')
            assumptions = []
        # Design-level threshold: a conditional result with its assumptions written down is enough to
        # draw the schematic; proving it under every guaranteed condition belongs to independent review.
        if conclusion == 'conditional' and not (omitted or assumptions):
            error('conditional_without_assumptions', key)
        # Conditional is not a hedge: it names the guarantee the datasheet or the
        # requirement does not give; partial coverage names what was left out.
        if conclusion == 'conditional' and not (isinstance(row.get('missing_guarantee'), str) and row['missing_guarantee'].strip()):
            error('conditional_without_missing_guarantee', key)
        if coverage == 'partial' and not omitted:
            error('partial_without_omitted_terms', key)
        linked(row, 'refs', refs, True)
        # The conclusion follows from the numbers: each check compares a computed
        # value with the limit it must meet. A failed check cannot be called
        # conditional, and a calculation without any check proves nothing.
        checks = row.get('checks')
        if not isinstance(checks, list) or not checks:
            error('missing_checks', key)
            checks = []
        results, sides = [], set()
        for i, c in enumerate(checks):
            where = key + ':checks[' + str(i) + ']'
            if (not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip()
                    or not finite(c.get('value')) or not finite(c.get('limit'))
                    or c.get('operator') not in OPERATORS or not isinstance(c.get('unit'), str)):
                error('schema', where + ' needs name, finite value/limit, operator (<=, <, >=, >) and unit')
                continue
            results.append(OPERATORS[c['operator']](c['value'], c['limit']))
            if c.get('side') is not None:
                if c['side'] not in WINDOW_SIDES:
                    error('schema', where + ':side must be no_false_trip or protection')
                sides.add(c['side'])
        if results and conclusion in ('supported', 'conditional') and not all(results):
            error('conclusion_contradicts_checks', key)
        if results and conclusion == 'failed' and all(results):
            error('conclusion_contradicts_checks', key)
        # A threshold has two sides: normal operation must stay clear of the
        # minimum trip point, and the maximum trip point must still protect.
        if row.get('kind') == 'threshold':
            for side in WINDOW_SIDES:
                if side not in sides:
                    error('threshold_window_incomplete', key + ':' + side)
        elif row.get('kind') is not None:
            error('schema', key + ':kind must be threshold when present')
        if conclusion == 'failed':
            need('calculation_failed', key)
            for rid in row.get('requirements', []):
                if rid in requirements and requirements[rid].get('status') == 'design_supported':
                    error('unsupported_calculation_dependency', rid + ':' + key)
    covered = {r for row in calculations.values() if isinstance(row.get('refs'), list) for r in row['refs']}
    for ref in threshold_parts:
        if ref not in covered:
            error('threshold_part_uncalculated', ref)
    if not calculations and not record.get('no_calculations_reason'):
        need('calculation_scope_missing', 'Declare necessary calculations or explain why none apply')
    if record.get('coverage') not in ('complete', 'partial'):
        error('schema', 'coverage must be complete or partial')
    if record.get('coverage') != 'complete':
        need('partial_review', 'Not all requirements/design obligations reviewed')
    convergence = {'status': 'NOT_ASSESSED'}
    if 'convergence_version' in record:
        if record['convergence_version'] != 1:
            error('schema', 'convergence_version must be 1')
        else:
            convergence = frontier(work, evidence)
            errors.extend(convergence['errors'])
    status = 'FAIL' if errors else 'INCOMPLETE' if pending else 'PASS'
    if record.get('claim') not in ('candidate', 'design_closed'):
        error('schema', 'claim must be candidate or design_closed')
        status = 'FAIL'
    if record.get('claim') == 'design_closed' and status != 'PASS':
        error('false_design_closure', 'Design closure claimed with unresolved work or invalid evidence')
        status = 'FAIL'
    return {'status': status, 'scope': 'Declared design evidence and dependency consistency; not physics, native ERC or visual approval',
            'intent_sha256': sha256(intent_path), 'errors': errors, 'pending': pending,
            'pcb_handoffs': [k for k, v in work.items() if v.get('stage') == 'pcb' and v.get('status') == 'handoff'],
            'counts': {k: len(v) for k, v in tables.items()}, 'convergence': convergence,
            'parameters': 'CHECKED' if parameters else 'NOT_CHECKED',
            'unspecified_operations': sorted(k for k, v in points.items() if v.get('specified') is False),
            'downstream_handoffs': [k for k, v in work.items() if v.get('stage') in ('validation', 'pcb') and v.get('status') == 'handoff']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('record', type=Path)
    ap.add_argument('--intent', type=Path, required=True)
    ap.add_argument('--artifact-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    try:
        result = audit(json.loads(args.record.read_text(encoding='utf-8')), args.intent, args.artifact_root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'FAIL', 'errors': [{'code': 'invalid_input', 'item': str(exc)}], 'pending': []}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
