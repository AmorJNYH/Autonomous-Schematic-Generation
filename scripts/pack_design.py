#!/usr/bin/env python3
"""Check a delivery folder has exactly the fixed shape, then write record/manifest.json.

    <delivery>/
      设计报告.md     render_design_report.py
      原理图/         KiCad project, schematic.pdf, netlist.xml, BOM.csv
      设计资料/       design documents that stay valid across versions
      record/         intent, design closure (+ audit), summary.json, visual review,
                      review responses, cited calculations and page scripts, manifest.json

Requirements, datasheets and the previous version are referenced by path + SHA-256, never
copied. Anything else at the top level, history snapshots, logs, oversized files and design
evidence that the closure record cites but the folder does not contain all fail the pack.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_design_closure import audit  # noqa: E402
from render_design_report import REPORT, REQUIRED, render  # noqa: E402

TOP = (REPORT, '原理图', '设计资料', 'record')
SCHEMATIC = ('schematic.pdf', 'netlist.xml', 'BOM.csv')
RECORD_DIRS = ('calculations', 'scripts', 'evidence')
MAX_BYTES = 10 * 1024 * 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(path):
    path = Path(path).resolve()
    if path.is_file():
        return {'path': str(path), 'kind': 'file', 'sha256': sha256(path)}
    files = sorted(p for p in path.rglob('*') if p.is_file() and not p.name.startswith('.'))
    tree = hashlib.sha256()
    for p in files:
        tree.update(('%s\0%s\n' % (p.relative_to(path).as_posix(), sha256(p))).encode())
    return {'path': str(path), 'kind': 'directory', 'files': len(files), 'tree_sha256': tree.hexdigest()}


def skill_version():
    try:
        return subprocess.run(['git', '-C', str(Path(__file__).resolve().parents[1]), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def check(root, inputs=()):
    root = Path(root)
    errors = []
    present = {p.name for p in root.iterdir() if not p.name.startswith('.')} if root.is_dir() else set()
    extra = sorted(present - set(TOP))
    if extra:
        errors.append('only %s belong at the top level; move these to the work directory or reference them '
                      'with --input: %s' % (', '.join(TOP), ', '.join(extra)))
    for name in TOP:
        if name not in present:
            errors.append('missing %s%s' % (name, '; run render_design_report.py' if name == REPORT else ''))
    sch = root / '原理图'
    if sch.is_dir():
        if not list(sch.glob('*.kicad_pro')):
            errors.append('原理图/ has no .kicad_pro')
        for name in SCHEMATIC:
            if not (sch / name).is_file():
                errors.append('原理图/%s is missing' % name)
    record = root / 'record'
    if record.is_dir():
        for name in REQUIRED + ('delivery-evidence.json',):
            if not (record / name).is_file():
                errors.append('record/%s is missing' % name)
        for p in record.iterdir():
            if p.is_dir() and p.name not in RECORD_DIRS:
                errors.append('record/%s/ is not a delivery folder (allowed: %s)' % (p.name, ', '.join(RECORD_DIRS)))
    for p in sorted(root.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if p.suffix == '.log':
            errors.append('%s: logs stay in the work directory' % rel)
        elif p.stat().st_size > MAX_BYTES:
            errors.append('%s is %.1f MB; keep only what the design cites, reference large inputs with --input'
                          % (rel, p.stat().st_size / 1e6))
    intent, closure = record / 'electrical-intent.json', record / 'design-closure.json'
    if intent.is_file() and closure.is_file():
        try:
            result = audit(json.loads(closure.read_text(encoding='utf-8')), intent, root, inputs)
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append('design-closure.json cannot be audited: %s' % error)
        else:
            if result['status'] == 'FAIL':
                errors.append('design-closure.json fails inside the delivery (cited evidence must be in this folder, '
                              'paths relative to it, or in an --input): ' + '; '.join('%s %s' % (e['code'], e['item'])
                                                                    for e in result['errors'][:5]))
    if (root / REPORT).is_file() and record.is_dir():
        _, problems = render(root)
        errors += ['report records: ' + p for p in problems]
    return errors


def pack(root, inputs):
    root = Path(root)
    errors = check(root, list(inputs.values()))
    declared = {}
    for name, path in inputs.items():
        if not Path(path).exists():
            errors.append('input %s does not exist: %s' % (name, path))
        else:
            declared[name] = fingerprint(path)
    if errors:
        return errors, None
    packed = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*'))
              if p.is_file() and p.name != 'manifest.json'}
    manifest = {'schema_version': 1, 'skill_version': skill_version(), 'inputs': declared, 'packed': packed}
    (root / 'record' / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                                   encoding='utf-8')
    return [], manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('delivery')
    parser.add_argument('--input', action='append', default=[], metavar='NAME=PATH',
                        help='requirements, datasheets, previous version ... (referenced, not copied)')
    args = parser.parse_args(argv)
    errors, _ = pack(args.delivery, dict(item.split('=', 1) for item in args.input))
    for e in errors:
        print('ERROR:', e)
    print('FAIL' if errors else 'PASS')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
