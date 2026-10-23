#!/usr/bin/env python3
"""The newest entry of docs/improvement-ledger.md names its event, its causes and its files.

A skill change happens because of an event (a review comment, a datasheet
page, a test result, a user correction), is attributed to a cause class, and
touches files that exist. Older entries are history and are not checked.

The ASG 纲要 (SKILL.md) and the 绘图纲要 O1-O8 (drawing-recipes.md) change only
with a person's approval: the newest entry that carries `Outline:` must name
the current outline hash and an `Approved: user:<date>`.
"""

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / 'docs' / 'improvement-ledger.md'
CAUSES = ('rule_missing', 'rule_not_enforced', 'knowledge_missing', 'knowledge_wrong', 'judgment')
SOURCE = re.compile(r'(review:[^\s/,;]+/[^\s,;]+|datasheet:[^\s,;]+#p\d+|test:[^\s,;]+|user:\d{4}-\d{2}-\d{2})')
# (file, heading) of each outline section; a section runs to the next level-2 heading.
OUTLINE = (('SKILL.md', '## ASG 纲要（核心标准）'), ('references/drawing-recipes.md', '## Outline rules (how to decide the structure)'))
APPROVED = re.compile(r'user:\d{4}-\d{2}-\d{2}')


def outline_hash(root=ROOT):
    digest = hashlib.sha256()
    for name, heading in OUTLINE:
        text = (root / name).read_text(encoding='utf-8')
        start = text.find('\n' + heading + '\n')
        if start < 0:
            raise ValueError('%s: heading %r not found' % (name, heading))
        end = text.find('\n## ', start + len(heading) + 2)
        digest.update(text[start:end if end >= 0 else len(text)].strip().encode('utf-8'))
    return digest.hexdigest()[:16]


def check_outline(text, root=ROOT):
    """The newest entry with an Outline: field approves the outline as it is now."""
    for entry in re.split(r'^## ', text, flags=re.M)[1:]:
        recorded = field(entry, 'Outline')
        if not recorded:
            continue
        title = entry.splitlines()[0].strip()
        problems = []
        if recorded != outline_hash(root):
            problems.append('%s: Outline: %s is not the current outline %s; 纲要改动须先经人确认并写新的台账条目'
                            % (title, recorded, outline_hash(root)))
        if not APPROVED.search(field(entry, 'Approved')):
            problems.append('%s: Approved: must cite user:<date>' % title)
        return problems
    return ['no ledger entry records an approved Outline: hash']


def latest_entry(text):
    parts = re.split(r'^## ', text, flags=re.M)
    return parts[1] if len(parts) > 1 else ''


def field(entry, name):
    m = re.search(r'^[-*\s]*%s:\s*(.+?)(?=^\S|^[-*]\s+\w+:|\Z)' % name, entry, flags=re.M | re.S)
    return ' '.join(m.group(1).split()) if m else ''


def check_entry(entry, root=ROOT):
    problems = []
    title = entry.splitlines()[0].strip() if entry.strip() else ''
    event, causes, changed = field(entry, 'Event'), field(entry, 'Causes'), field(entry, 'Changed')
    if not SOURCE.search(event):
        problems.append('%s: Event: must cite review:<dir>/<item>, datasheet:<path>#p<n>, test:<record> or user:<date>' % title)
    if not any(re.search(r'%s\s+\d+' % c, causes) for c in CAUSES):
        problems.append('%s: Causes: must count the cause classes (%s)' % (title, ', '.join(CAUSES)))
    paths = [p.strip('`') for p in re.split(r'[\s,;]+', changed) if p.strip('`')]
    if not paths:
        problems.append('%s: Changed: must list the files changed' % title)
    for p in paths:
        if not (root / p).exists():
            problems.append('%s: Changed: %s does not exist' % (title, p))
    return problems


def main(argv=None):
    argv = list(argv or [])
    if argv[:1] == ['--outline-hash']:
        print(outline_hash())
        return 0
    path = Path(argv[0]) if argv else LEDGER
    text = path.read_text(encoding='utf-8')
    problems = check_entry(latest_entry(text)) + check_outline(text)
    for p in problems:
        print('PROBLEM:', p)
    print('FAIL' if problems else 'PASS')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
