"""Ordering status of each part, read from its own datasheet.

A datasheet that lists an MPN under DISCONTINUED, OBSOLETE, NOT RECOMMENDED FOR NEW DESIGN,
END OF LIFE, LAST TIME BUY or NRND marks it unfit for a new design. Such a heading opens a block
that runs to the next footnote line (†, *, a numbered note) or two blank lines; an MPN listed in
the block, or on the same line as the marker, is flagged. Prose that only mentions the word
("some devices have been discontinued") does not open a block.
"""

import re
import shutil
import subprocess

from .discrete_semantics import resolve

MARKER = re.compile(r'discontinued|obsolete|not\s+recommended\s+for\s+new\s+designs?|end[\s-]of[\s-]life'
                    r'|last[\s-]time[\s-]buy|\bNRND\b|停产', re.I)
HEADING = re.compile(r'^(?:%s)' % MARKER.pattern, re.I)
FOOTNOTE = re.compile(r'^(?:†|\*|\d+\.\s)')
_texts = {}


def full_text(path):
    if path not in _texts:
        tool = shutil.which('pdftotext')
        r = subprocess.run([tool, '-layout', '-q', str(path), '-'], capture_output=True, text=True,
                           timeout=120) if tool and path.is_file() else None
        _texts[path] = r.stdout if r is not None and r.returncode == 0 else None
    return _texts[path]


def flagged(mpn, text):
    """The marker line under which the datasheet lists ``mpn``, or None."""
    token = re.compile(r'(?<![A-Za-z0-9-])%s(?![A-Za-z0-9-])' % re.escape(mpn), re.I)   # ABC100 is not ABC100-TR
    heading, blanks = None, 0
    for line in text.splitlines():
        s = line.strip()
        if not s:
            blanks += 1
            if blanks >= 2:
                heading = None
            continue
        blanks = 0
        if HEADING.match(s) and len(s.split()) <= 6:
            heading = s
        elif FOOTNOTE.match(s):
            heading = None
        if token.search(s) and (heading or MARKER.search(s)):
            return heading or s
    return None


def audit(intent, bases=()):
    """{flagged: [{ref, mpn, datasheet, marker, reason}], not_checked: [reason]} over parts with an MPN and a datasheet."""
    found, unchecked = [], []
    if not shutil.which('pdftotext'):
        return {'flagged': [], 'not_checked': ['没有 pdftotext，料号的停产状态没核对']}
    for comp in intent.get('components') or []:
        if not isinstance(comp, dict):
            continue
        mpn, sheet = comp.get('mpn'), comp.get('datasheet')
        if not (isinstance(mpn, str) and mpn.strip() and isinstance(sheet, str) and sheet.strip()):
            continue
        path = resolve(sheet, bases)
        text = full_text(path) if path else None
        if text is None:
            unchecked.append('%s 的手册 %s 读不出文字，停产状态没核对' % (comp.get('ref'), sheet))
            continue
        marker = flagged(mpn.strip(), text)
        if marker:
            found.append({'ref': comp.get('ref'), 'mpn': mpn.strip(), 'datasheet': sheet, 'marker': marker,
                          'reason': comp.get('lifecycle_reason')})
    return {'flagged': found, 'not_checked': unchecked}
