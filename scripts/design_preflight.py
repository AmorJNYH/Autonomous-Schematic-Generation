"""Calculation-condition record, v1. No electrical signoff.

Self-contained so it can be vendored unchanged wherever it is needed.
Arithmetic is bounded AST evaluation, never eval or executable source input.
"""
import ast
import math
import operator

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
COMPARISONS = {'>=': operator.ge, '<=': operator.le, '>': operator.gt, '<': operator.lt}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def evidence(value):
    return isinstance(value, list) and bool(value) and all(isinstance(x, dict) and
        text(x.get('source')) and text(x.get('locator')) for x in value)


def calculate(expression, values):
    if not text(expression):
        raise ValueError('arithmetic expression required')
    root = ast.parse(expression, mode='eval')
    def visit(node):
        if isinstance(node, ast.Constant) and number(node.value):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        raise ValueError('unsupported expression/name')
    try:
        value = visit(root.body)
    except (ZeroDivisionError, OverflowError) as exc:
        raise ValueError('undefined arithmetic') from exc
    if not number(value):
        raise ValueError('nonfinite arithmetic')
    return value


def validate_calculations(rows):
    errors, results = [], {}
    if not isinstance(rows, list):
        return ['calculations must be an array'], results
    for row in rows:
        if not isinstance(row, dict) or not text(row.get('id')):
            errors.append('calculation needs an id'); continue
        key = row['id']
        start = len(errors)
        if key in results:
            errors.append(key + ': duplicate calculation id'); continue
        limitations = []
        if not all(text(row.get(k)) for k in ('model', 'output_unit')):
            errors.append(key + ': model and output_unit required')
        inputs = row.get('inputs')
        if not isinstance(inputs, dict) or not inputs:
            errors.append(key + ': inputs must be a nonempty object'); inputs = {}
        values = {}
        for name, param in inputs.items():
            label = key + '/' + name
            if (not isinstance(param, dict) or not number(param.get('value'))
                    or not text(param.get('unit')) or not evidence(param.get('evidence'))):
                errors.append(label + ': finite value/unit/locatable evidence required'); continue
            values[name] = param['value']
            basis = param.get('basis')
            if basis not in ('GUARANTEED', 'DERIVED_BOUND', 'ASSUMED', 'TYPICAL'):
                errors.append(label + ': invalid basis')
            if basis in ('ASSUMED', 'TYPICAL'):
                limitations.append(label + ': ' + basis)
            if basis == 'DERIVED_BOUND' and not text(param.get('derivation')):
                errors.append(label + ': derived bound needs derivation and evidence')
            # Only a guaranteed or derived bound has test conditions the design must stay inside.
            bound_basis = basis in ('GUARANTEED', 'DERIVED_BOUND')
            conditions, actual = param.get('conditions', {}), param.get('operating_conditions', {})
            if not isinstance(conditions, dict) or not isinstance(actual, dict) or (
                    bound_basis and not ('conditions' in param and 'operating_conditions' in param)):
                errors.append(label + ': conditions and operating_conditions required'); continue
            if bound_basis and not conditions and not text(param.get('unconditional_basis')):
                errors.append(label + ': empty conditions need unconditional_basis')
            for dimension, bound in conditions.items():
                actual_bound = actual.get(dimension)
                def valid_range(x):
                    return (isinstance(x, dict) and text(x.get('unit')) and number(x.get('min'))
                            and number(x.get('max')) and x['min'] <= x['max'])
                if not valid_range(bound):
                    errors.append(label + ': invalid guarantee range ' + dimension); continue
                if not valid_range(actual_bound):
                    limitations.append(label + ': missing operating range ' + dimension); continue
                if actual_bound['unit'] != bound['unit']:
                    errors.append(label + ': unit mismatch ' + dimension)
                elif not (bound['min'] <= actual_bound['min'] <= actual_bound['max'] <= bound['max']):
                    limitations.append(label + ': outside guarantee range ' + dimension)
        assumptions = row.get('assumptions')
        if not isinstance(assumptions, list) or not all(text(x) for x in assumptions):
            errors.append(key + ': assumptions must be an array of strings')
        elif assumptions:
            limitations.extend(assumptions)
        try:
            value = calculate(row.get('expression'), values)
        except (ValueError, SyntaxError, TypeError, RecursionError) as exc:
            errors.append(key + ': ' + str(exc)); value = None
        acceptance = row.get('acceptance')
        passed = None
        if (not isinstance(acceptance, dict) or acceptance.get('operator') not in COMPARISONS
                or not number(acceptance.get('value')) or acceptance.get('unit') != row.get('output_unit')):
            errors.append(key + ': acceptance needs comparison, finite value and matching output unit')
        elif value is not None:
            passed = COMPARISONS[acceptance['operator']](value, acceptance['value'])
        status = 'INVALID' if len(errors) > start else ('CONDITIONAL' if limitations else ('SUPPORTED' if passed else 'FAIL'))
        if limitations and not text(row.get('closure')):
            errors.append(key + ': conditional calculation needs closure method')
        results[key] = {'status': status, 'value': value, 'acceptance_met': passed, 'limitations': limitations}
    return errors, results
