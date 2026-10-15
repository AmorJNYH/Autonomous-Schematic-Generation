"""Identify executable design work; this is dependency accounting, not design approval."""

def frontier(work, evidence):
    errors, ready, blocked, external = [], [], {}, []
    def err(code, item):
        errors.append({'code': code, 'item': item})
    edges = {}
    for key, row in work.items():
        deps = row.get('blocked_by')
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            err('convergence_dependencies', key)
            deps = []
        edges[key] = deps
        for dep in deps:
            if dep not in work:
                err('convergence_unknown_dependency', key + ':' + dep)
        if row.get('stage') == 'external' and row.get('status') != 'closed':
            external.append(key)
            alternatives = row.get('fallback_work')
            assessed = row.get('fallback_evidence')
            if not isinstance(alternatives, list) or any(not isinstance(v, str) for v in alternatives):
                err('convergence_fallback_work', key)
                alternatives = []
            for alt in alternatives:
                if alt not in work or work[alt].get('stage') != 'design':
                    err('convergence_invalid_fallback', key + ':' + alt)
            if not alternatives and (not isinstance(assessed, list) or not assessed or
                                     any(not isinstance(v, str) or v not in evidence for v in assessed)):
                err('convergence_unassessed_fallback', key)
    seen, stack = set(), set()
    def visit(key):
        if key in stack:
            err('convergence_cycle', key)
            return
        if key in seen:
            return
        stack.add(key)
        for dep in edges.get(key, []):
            if dep in work:
                visit(dep)
        stack.remove(key)
        seen.add(key)
    for key in work:
        visit(key)
    for key, row in work.items():
        if row.get('stage') != 'design' or row.get('status') != 'open':
            continue
        pending = [v for v in edges[key] if v in work and work[v].get('status') != 'closed']
        if pending:
            blocked[key] = pending
        else:
            ready.append(key)
    # Never interpret unassessed alternatives, cycles or unknown IDs as an external stop.
    status = ('INVALID' if errors else 'CONTINUE_DESIGN' if ready else
              'WAITING_DEPENDENCIES' if blocked else 'NO_OPEN_DESIGN_ACTIONS')
    return {'status': status, 'ready_design_actions': ready, 'blocked_design_actions': blocked,
            'external_inputs': external, 'errors': errors,
            'scope': 'Declared action dependencies only; no electrical closure or PCB release.'}
