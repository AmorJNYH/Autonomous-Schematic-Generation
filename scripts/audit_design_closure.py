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
from schematic_layout.citations import check_source


SEVERITIES = ('P0', 'P1', 'P2', 'P3')
# What happens if an open item is left undone, and when it shows; the level follows from the two.
CONSEQUENCES = ('safety', 'damage', 'function', 'margin', 'optimization')
OCCURRENCES = ('normal', 'condition', 'fault')
SEVERITY_RULE = {'safety': ('P0', 'P0', 'P0'), 'damage': ('P0', 'P0', 'P1'), 'function': ('P1', 'P1', 'P2'),
                 'margin': ('P2', 'P2', 'P3'), 'optimization': ('P3', 'P3', 'P3')}


def severity_of(row):
    """P0-P3 from consequence_class and occurrence, or None when either is missing or unknown."""
    consequence, occurrence = row.get('consequence_class'), row.get('occurrence')
    if consequence not in CONSEQUENCES or occurrence not in OCCURRENCES:
        return None
    return SEVERITY_RULE[consequence][OCCURRENCES.index(occurrence)]
OPERATORS = {'<=': lambda v, l: v <= l, '<': lambda v, l: v < l,
             '>=': lambda v, l: v >= l, '>': lambda v, l: v > l}
# Parts whose job is to set or clamp a voltage. Each one needs a calculation
# naming it, so a protection threshold cannot ship as prose only.
THRESHOLD_PART = re.compile(r'zener|tvs|tl431|atl431|lm4040|shunt.?ref|voltage.?ref|^power:vref', re.I)
# The same parts drawn with a generic diode or IC symbol, known by their series prefix.
THRESHOLD_SERIES = re.compile(r'^(1N47|1N52|1N53|1SMA|BZX|BZT|BZV|MMSZ|SMAJ|SMBJ|SMCJ|SMF|P6KE|P4SMA|P6SMB|PESD|TPD|ESD|'
                              r'TL431|TLV431|ATL431|AZ431|LM385|LM4040|LM4041|REF30|REF50)', re.I)


def threshold_part(c):
    """A part whose job is to set or clamp a voltage: by symbol, series prefix or a declared role."""
    return bool(THRESHOLD_PART.search(str(c.get('lib_id', '')))
                or any(THRESHOLD_SERIES.match(str(c.get(k, '')).strip()) for k in ('value', 'mpn'))
                or (c.get('fields') or {}).get('ComponentRole') == 'threshold')
WINDOW_SIDES = ('no_false_trip', 'protection')
# Where each number in a calculation comes from (parameter_version 1). A device
# parameter cites the datasheet page it was read from; one the datasheet does
# not give is "unspecified" and ties to a recorded operating-point decision.
# Version 2 adds requirement inputs and physical constants, no longer filed as models.
PARAMETER_BASES = ('guaranteed', 'typical', 'derived', 'design_choice', 'model', 'unspecified')
PARAMETER_BASES_V2 = PARAMETER_BASES + ('requirement', 'constant')
# Version 2: the conclusion follows from the inputs. A typical or unspecified device value, or an open
# vendor-data item, leaves it resting on the vendor; an engineering model or a term not calculated
# leaves it resting on ASG's own estimate; otherwise the design holds.
VENDOR_BASES, ESTIMATE_BASES = ('typical', 'unspecified'), ('model',)
OMISSION_KINDS = ('not_calculated', 'verify_by_test')
DATASHEET = re.compile(r'^datasheet:.+#p\d+$')
# Where a data gap was found (gap_version 1): a datasheet page, a review item or a user decision.
GAP_SOURCE = re.compile(r'^(datasheet:.+#p\d+|review:[^/\s]+/\S+|user:\d{4}-\d{2}-\d{2})$')
GAP_FIELDS = ('missing', 'why_external', 'calculations', 'consequence', 'questions', 'owner', 'fallback', 'action')
# A requirement question put to the user (requirement-clarifications.md) is answered in one of three ways.
DECISIONS = ('DECIDED', 'ADOPTED_PROPOSAL', 'DEFERRED')
CLARIFICATION_ID = re.compile(r'^CL-\S+$')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Whether the user let ASG write a decided requirement into the original requirement files.
FILE_DECISIONS = ('UPDATED', 'KEPT')


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


def calculation_basis(row, vendor_items=(), deferred_items=()):
    """(conclusion, rests_on, reasons) a parameter_version 2 calculation follows to.

    ``vendor_items`` are the open external work items whose ``calculations`` name this one;
    ``deferred_items`` the open requirement work items (requirements the user deferred) that do.
    """
    failing = [c.get('name') for c in row.get('checks') or [] if isinstance(c, dict) and c.get('operator') in OPERATORS
               and finite(c.get('value')) and finite(c.get('limit')) and not OPERATORS[c['operator']](c['value'], c['limit'])]
    if failing:
        return 'failed', None, failing
    params = [p for p in row.get('parameters') or [] if isinstance(p, dict)]
    vendor = [p.get('name') for p in params if p.get('basis') in VENDOR_BASES] + ['待办 %s' % w for w in vendor_items]
    estimate = [p.get('name') for p in params if p.get('basis') in ESTIMATE_BASES]
    estimate += ['没算：%s' % o.get('term') for o in row.get('omitted_terms') or []
                 if isinstance(o, dict) and o.get('kind') == 'not_calculated']
    deferred = ['待办 %s' % w for w in deferred_items]
    if vendor:
        return 'conditional', 'vendor_data', vendor + deferred + estimate
    if deferred:
        return 'conditional', 'user_deferred', deferred + estimate
    if estimate:
        return 'conditional', 'estimate', estimate
    return 'supported', None, []


def vendor_items_of(work, stage='external'):
    """{calculation id: [open work item ids of this stage naming it]}; external by default."""
    found = {}
    for key, row in work.items():
        if row.get('stage') == stage and row.get('status') != 'closed' and isinstance(row.get('calculations'), list):
            for cid in row['calculations']:
                found.setdefault(cid, []).append(key)
    return found


def audit_clarifications(record, requirements, work, error):
    """Requirement questions put to the user: each one answered, the answer written back as a requirement,
    or, when the user deferred it, carried by an open requirement work item on the proposed text."""
    rows = record.get('clarifications', [])
    if not isinstance(rows, list):
        error('schema', 'clarifications must be a list')
        return {}
    found = {}
    for row in rows:
        if not isinstance(row, dict) or not (isinstance(row.get('id'), str) and CLARIFICATION_ID.match(row['id'])):
            error('schema', 'clarifications entry requires an id CL-<name>')
            continue
        key = row['id']
        if key in found:
            error('duplicate_id', 'clarifications:' + key)
        found[key] = row
        for field in ('found_in', 'question', 'requirement_text', 'proposed_requirement'):
            if not text(row.get(field)):
                error('schema', key + ':needs ' + field)
        ids = row.get('requirement_ids')
        if not isinstance(ids, list) or not all(isinstance(r, str) for r in ids):
            error('schema', key + ':requirement_ids must be a string list')
            ids = []
        for rid in ids:
            if rid not in requirements:
                error('unknown_requirement_ids', key + ':' + rid)
        answer = row.get('answer')
        if answer is None:
            error('clarification_unanswered', key)
            continue
        source = answer.get('source') if isinstance(answer, dict) else None
        if (not isinstance(answer, dict) or answer.get('decision') not in DECISIONS
                or not text(answer.get('text')) or not text(answer.get('by'))
                or not (isinstance(answer.get('date'), str) and DATE.match(answer['date']))
                or not (isinstance(source, dict) and text(source.get('source')) and text(source.get('locator')))):
            error('schema', key + ':answer needs decision (%s), text, by, date YYYY-MM-DD and source {source, locator}'
                  % '/'.join(DECISIONS))
            continue
        if answer['decision'] == 'ADOPTED_PROPOSAL' and answer['text'] != row.get('proposed_requirement'):
            error('adopted_text_differs', key)
        if answer['decision'] != 'DEFERRED':
            if requirements.get(key, {}).get('text') != answer['text']:
                error('clarification_not_written_back', key)
            files = answer.get('requirement_files')
            if not isinstance(files, dict) or files.get('decision') not in FILE_DECISIONS:
                error('requirement_files_not_asked', key)
            elif files['decision'] == 'UPDATED' and not (
                    isinstance(files.get('files'), list) and files['files'] and all(text(f) for f in files['files'])):
                error('requirement_files_without_files', key)
            continue
        if not any(w.get('stage') == 'requirement' and w.get('status') == 'open' and w.get('clarification') == key
                   for w in work.values()):
            error('deferred_without_requirement_item', key)
        for rid in ids:
            if requirements.get(rid, {}).get('status') == 'design_supported':
                error('deferred_requirement_claimed_supported', key + ':' + rid)
    return found


def audit_omissions(key, row, work, error):
    """Version 2 omitted terms: a term not calculated is open design work, or open vendor data it waits for;
    one only a test can settle is handed off."""
    omitted = row.get('omitted_terms', [])
    if not isinstance(omitted, list):
        error('schema', key + ':omitted_terms must be a list')
        return []
    kinds = []
    for i, o in enumerate(omitted):
        if not isinstance(o, dict) or not text(o.get('term')) or o.get('kind') not in OMISSION_KINDS:
            error('schema', key + ':omitted_terms[%d] needs term and kind (%s)' % (i, '/'.join(OMISSION_KINDS)))
            continue
        kinds.append(o['kind'])
        item = work.get(o.get('work_item'), {})
        if o['kind'] == 'verify_by_test' and not (item.get('stage') == 'validation' and item.get('status') == 'handoff'):
            error('verify_by_test_without_validation_handoff', key + ':' + o['term'])
        if o['kind'] == 'not_calculated' and not (item.get('stage') in ('design', 'external') and item.get('status') == 'open'):
            error('not_calculated_without_design_item', key + ':' + o['term'])
    return kinds


def audit_parameters(key, row, refs, points, calculations, error, version=1, requirements=()):
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
        bases = PARAMETER_BASES_V2 if version == 2 else PARAMETER_BASES
        if basis not in bases:
            error('schema', where + ':basis must be one of ' + '/'.join(bases))
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
        if basis in ('model', 'constant') and not text(p.get('reason')):
            error(basis + '_parameter_without_reason', where)
        if basis == 'requirement' and not (isinstance(p.get('source'), str) and p['source'].startswith('req:')
                                           and p['source'][4:] in requirements):
            error('requirement_parameter_without_requirement', where)
        if basis == 'unspecified':
            point = points.get(p.get('operating_point'))
            if not point or point.get('specified') is not False:
                error('unspecified_parameter_without_operating_point', where)
        if version == 1 and basis in ('typical', 'unspecified') and row.get('conclusion') == 'supported':
            error('supported_with_unguaranteed_parameter', where)


def audit_gaps(work, calculations, error):
    """Open external items say which data is missing, why only the owner has it and what to ask."""
    fallbacks = {}
    for key, row in work.items():
        if row.get('stage') != 'external' or row.get('status') == 'closed':
            continue
        for field in GAP_FIELDS:
            value = row.get(field)
            # A behaviour or qualification gap that no calculation rests on says so instead of linking one.
            if field == 'calculations' and value == [] and text(row.get('no_calculation_reason')):
                continue
            if not (text(value) or (isinstance(value, list) and value)):
                error('gap_missing_fields', key + ':' + field)
        for i, m in enumerate(row.get('missing') if isinstance(row.get('missing'), list) else []):
            if not isinstance(m, dict) or not all(text(m.get(f)) for f in ('source', 'given', 'needed')):
                error('schema', key + ':missing[%d] needs source, given and needed' % i)
            elif not GAP_SOURCE.match(m['source']):
                error('gap_bad_source', key + ':missing[%d]' % i)
        for field in ('questions', 'calculations'):
            if isinstance(row.get(field), list) and not all(text(x) for x in row[field]):
                error('schema', key + ':' + field + ' must be a nonempty string list')
        for cid in row.get('calculations') if isinstance(row.get('calculations'), list) else []:
            if calculations.get(cid, {}).get('conclusion') != 'conditional':
                error('gap_unlinked_calculation', key + ':' + str(cid))
        if text(row.get('fallback')):
            fallbacks.setdefault(' '.join(row['fallback'].split()), []).append(key)
    for keys in fallbacks.values():
        if len(keys) > 1:
            error('gap_generic_fallback', '、'.join(keys))


def audit_citations(record, calculations, work, extra, error):
    """Each datasheet citation names a file in the library and a page it has; cited values are looked up."""
    cited = [('operating_points:%s' % r.get('id'), r.get('source'), ())
             for r in record.get('operating_points') or [] if isinstance(r, dict)]
    cited += [('%s:%s' % (key, p.get('name')), p.get('source'), (p.get('value'),) if p.get('basis') in ('guaranteed', 'typical') else ())
              for key, row in calculations.items() for p in row.get('parameters') or [] if isinstance(p, dict)]
    cited += [('%s:missing[%d]' % (key, i), m.get('source'), ())
              for key, row in work.items() for i, m in enumerate(row.get('missing') or []) if isinstance(m, dict)]
    summary = {'checked': 0, 'not_checked': [], 'review': []}
    for where, source, values in cited:
        result = check_source(source, values, extra)
        if result is None:
            continue
        summary['checked'] += 1
        if result['status'] == 'FAIL':
            error('citation_wrong', where + ': ' + result['reason'])
        elif result['reason'] and result['reason'] not in summary['not_checked']:   # not checked, or values not checked
            summary['not_checked'].append(result['reason'])
        if result['unshown']:
            summary['review'].append({'item': where, 'source': source, 'values': result['unshown']})
    return summary


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


def audit_calculation_v2(key, row, work, vendor_items, deferred_items, derived, error, need):
    """The written conclusion, rests_on and coverage must be the ones the record follows to."""
    kinds = audit_omissions(key, row, work, error)
    assumptions = row.get('assumptions', [])
    if not isinstance(assumptions, list) or any(not isinstance(x, str) for x in assumptions):
        error('schema', key + ':assumptions must be a string list')
    checks = row.get('checks')
    if not isinstance(checks, list) or not checks:
        error('missing_checks', key)
        checks = []
    sides = set()
    for i, c in enumerate(checks):
        where = key + ':checks[' + str(i) + ']'
        if (not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c['name'].strip()
                or not finite(c.get('value')) or not finite(c.get('limit'))
                or c.get('operator') not in OPERATORS or not isinstance(c.get('unit'), str)):
            error('schema', where + ' needs name, finite value/limit, operator (<=, <, >=, >) and unit')
            continue
        if c.get('side') is not None:
            if c['side'] not in WINDOW_SIDES:
                error('schema', where + ':side must be no_false_trip or protection')
            sides.add(c['side'])
    if row.get('kind') == 'threshold':
        for side in WINDOW_SIDES:
            if side not in sides:
                error('threshold_window_incomplete', key + ':' + side)
    elif row.get('kind') is not None:
        error('schema', key + ':kind must be threshold when present')
    conclusion, rests_on, reasons = calculation_basis(row, vendor_items, deferred_items)
    derived[key] = {'conclusion': conclusion, 'rests_on': rests_on, 'reasons': reasons}
    if (row.get('conclusion'), row.get('rests_on')) != (conclusion, rests_on):
        error('conclusion_not_derived', '%s: 写的 %s/%s，按记录是 %s/%s' % (
            key, row.get('conclusion'), row.get('rests_on'), conclusion, rests_on))
    coverage = 'partial' if 'not_calculated' in kinds else 'bounded'
    if row.get('coverage') != coverage:
        error('coverage_not_derived', '%s: 写的 %s，按遗漏项是 %s' % (key, row.get('coverage'), coverage))
    if conclusion == 'failed':
        need('calculation_failed', key)


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
    threshold_parts = sorted(c['ref'] for c in intent['components'] if threshold_part(c))
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
    clarifications = audit_clarifications(record, requirements, work, error)
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
                # Possible consequence if left undone; its level orders the report's to-do list.
                level = severity_of(row)
                if level is None:
                    error('missing_consequence', key)
                elif row.get('severity') not in (None, level):
                    error('severity_contradicts_rule', '%s: %s, rule gives %s' % (key, row['severity'], level))
        if stage == 'pcb':
            if row.get('scope') not in ('footprint_library', 'layout_implementation', 'dfm'):
                error('pcb_scope', key)
            prerequisites = linked(row, 'electrical_preconditions', work, True)
            for dep in prerequisites:
                item = work.get(dep, {})
                if item.get('stage') != 'design' or item.get('status') != 'closed':
                    error('pcb_electrical_precondition', key + ':' + dep)
        # A requirement the user deferred is designed on the proposed text; one never asked is asked now, not at delivery.
        if stage == 'requirement' and state != 'closed':
            asked = clarifications.get(row.get('clarification')) or {}
            if not text(row.get('assumption')):
                error('missing_assumption', key)
            if (asked.get('answer') or {}).get('decision') != 'DEFERRED':
                error('requirement_without_clarification', key)
            elif text(row.get('assumption')) and row['assumption'] != asked.get('proposed_requirement'):
                error('assumption_differs_from_proposal', key)
            if 'calculations' in row:
                linked(row, 'calculations', calculations)
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
    if parameters and record['parameter_version'] not in (1, 2):
        error('schema', 'parameter_version must be 1 or 2')
        parameters = False
    version = record['parameter_version'] if parameters else None
    points = audit_operating_points(record, work, refs, error, need) if parameters else {}
    vendor_items, deferred_items, derived = vendor_items_of(work), vendor_items_of(work, 'requirement'), {}
    for key, row in calculations.items():
        if parameters:
            audit_parameters(key, row, refs, points, calculations, error, version, requirements)
        linked(row, 'requirements', requirements, True)
        linked(row, 'evidence', evidence, True)
        coverage, conclusion = row.get('coverage'), row.get('conclusion')
        if coverage not in ('bounded', 'partial') or conclusion not in ('supported', 'conditional', 'failed'):
            error('schema', key + ':invalid coverage/conclusion')
        if version == 2:
            audit_calculation_v2(key, row, work, vendor_items.get(key, []), deferred_items.get(key, []), derived, error, need)
            continue
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
    if version == 2:
        for rid, req in requirements.items():
            weak = [k for k, row in calculations.items() if rid in (row.get('requirements') or [])
                    and derived.get(k, {}).get('conclusion') != 'supported']
            if req.get('status') == 'design_supported' and weak:
                error('requirement_status_not_derived', rid + ': rests on ' + '、'.join(weak))
    gaps = 'gap_version' in record
    if gaps and record['gap_version'] != 1:
        error('schema', 'gap_version must be 1')
        gaps = False
    if gaps:
        audit_gaps(work, calculations, error)
    citations = audit_citations(record, calculations, work, [root, *(inputs or ())], error)
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
    return {'status': status, 'scope': 'Declared design evidence and dependency consistency; not physics, native ERC or visual approval',
            'intent_sha256': sha256(intent_path), 'errors': errors, 'pending': pending,
            'severities': {k: severity_of(v) for k, v in work.items() if v.get('status') == 'open' and severity_of(v)},
            'pcb_handoffs': [k for k, v in work.items() if v.get('stage') == 'pcb' and v.get('status') == 'handoff'],
            'counts': {k: len(v) for k, v in tables.items()}, 'convergence': convergence,
            'parameters': 'CHECKED' if parameters else 'NOT_CHECKED', 'parameter_version': version,
            'calculation_basis': derived,
            'gaps': 'CHECKED' if gaps else 'NOT_CHECKED', 'citations': citations,
            'unspecified_operations': sorted(k for k, v in points.items() if v.get('specified') is False),
            'downstream_handoffs': [k for k, v in work.items() if v.get('stage') in ('validation', 'pcb') and v.get('status') == 'handoff']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('record', type=Path)
    ap.add_argument('--intent', type=Path, required=True)
    ap.add_argument('--artifact-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--input', action='append', default=[], metavar='NAME=PATH',
                    help='declared input (requirements, datasheets) where cited evidence may live, as pack_design takes it')
    args = ap.parse_args()
    inputs = [v.split('=', 1)[-1] for v in args.input]
    try:
        result = audit(json.loads(args.record.read_text(encoding='utf-8')), args.intent, args.artifact_root, inputs)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'status': 'FAIL', 'errors': [{'code': 'invalid_input', 'item': str(exc)}], 'pending': []}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
