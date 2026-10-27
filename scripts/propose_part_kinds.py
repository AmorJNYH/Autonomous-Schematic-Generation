#!/usr/bin/env python3
"""Propose kind declarations for the parts that need one (references/part-roles.md section 1).

For each key or special part without a verified declaration, read the first eight non-empty lines of page 1 of
its datasheet (title and product description) and list the kinds those lines name, each with the line as the
quote: fields.Kind, KindSource, KindQuote, plus the library subcategory its datasheet is filed under. The designer
checks a candidate and writes it into the design netlist; nothing here writes the netlist or counts as a
declaration (as schematic-review's datasheet_kinds.candidates, extracted text is never a conclusion).

    python3 propose_part_kinds.py <delivery> [--intent record/electrical-intent.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schematic_layout import part_classes as pc  # noqa: E402
from schematic_layout.citations import page_text  # noqa: E402

TITLE_LINES = 8


def propose(intent, bases):
    ctx = pc.context(intent)
    out = []
    for comp in intent.get('components') or []:
        if not isinstance(comp, dict):
            continue
        kind, level = pc.kind_of(comp)[0], pc.part_class(comp, ctx)
        if not pc.needs_declaration(comp, kind, level):
            continue
        if pc.verify_declaration(comp, kind, bases, pc.library_present())[0] == 'VERIFIED':
            continue
        row = {'ref': comp.get('ref'), 'inferred': kind, 'candidates': []}
        pdf = pc.find(comp.get('datasheet'), bases)
        if pdf is None:
            out.append(dict(row, status='no_document'))
            continue
        lines = [ln.strip() for ln in (page_text(pdf, 1) or '').splitlines() if ln.strip()][:TITLE_LINES]
        if not lines:
            out.append(dict(row, status='no_text'))
            continue
        source = 'datasheet:%s#p1' % comp['datasheet']
        # The title as a whole decides (a TVS title that also says "diode" is a TVS); the quote is the line naming it.
        for found in sorted(pc.cues(' '.join(lines))):
            quote = next((ln for ln in lines if found in pc.cues(ln, specific=False)), ' '.join(lines))
            row['candidates'].append({'Kind': found, 'KindSource': source, 'KindQuote': quote,
                                      'Category': pc.datasheet_category(comp)})
        kinds = [c['Kind'] for c in row['candidates']]
        row['status'] = 'none' if not kinds else 'single' if len(kinds) == 1 else 'multiple'
        row['agrees'] = kind in kinds
        out.append(row)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('delivery', type=Path)
    parser.add_argument('--intent', default='record/electrical-intent.json')
    args = parser.parse_args(argv)
    intent = json.loads((args.delivery / args.intent).read_text(encoding='utf-8'))
    print(json.dumps(propose(intent, [args.delivery, args.delivery / 'record']), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
