"""The newest improvement-ledger entry cites its event, counts its causes and lists existing files."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
import check_ledger  # noqa: E402

GOOD = """# ledger

## Thing (2026-10-19)

Prose about it.

- Event: review:SR-20261019-R3-改版前独立审查-41f4ad3/W-DRAW, user:2026-10-19
- Causes: rule_missing 1, knowledge_missing 2
- Changed: SKILL.md, scripts/render_design_report.py

## Older entry

no fields at all
"""


class LedgerTests(unittest.TestCase):
    def test_real_ledger_latest_entry_passes(self):
        text = check_ledger.LEDGER.read_text(encoding='utf-8')
        self.assertEqual([], check_ledger.check_entry(check_ledger.latest_entry(text)))

    def test_fields_are_required_and_files_must_exist(self):
        self.assertEqual([], check_ledger.check_entry(check_ledger.latest_entry(GOOD)))
        bad = GOOD.replace('review:SR-20261019-R3-改版前独立审查-41f4ad3/W-DRAW, user:2026-10-19', 'the R4 review') \
                  .replace('rule_missing 1, knowledge_missing 2', 'various') \
                  .replace('scripts/render_design_report.py', 'scripts/nope.py')
        problems = check_ledger.check_entry(check_ledger.latest_entry(bad))
        self.assertEqual(3, len(problems), problems)
        self.assertTrue(any('Event:' in p for p in problems))
        self.assertTrue(any('Causes:' in p for p in problems))
        self.assertTrue(any('scripts/nope.py does not exist' in p for p in problems))

    def test_outline_change_needs_approved_entry(self):
        current = check_ledger.outline_hash()
        approved = GOOD.replace('- Changed: SKILL.md, scripts/render_design_report.py',
                                '- Changed: SKILL.md\n- Approved: user:2026-10-23\n- Outline: %s' % current)
        self.assertEqual([], check_ledger.check_outline(approved))
        self.assertEqual(1, len(check_ledger.check_outline(GOOD)))
        stale = approved.replace(current, '0' * 16)
        self.assertTrue(any('not the current outline' in p for p in check_ledger.check_outline(stale)))
        unapproved = approved.replace('- Approved: user:2026-10-23\n', '')
        self.assertTrue(any('Approved:' in p for p in check_ledger.check_outline(unapproved)))

    def test_outline_hash_follows_outline_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, _ in check_ledger.OUTLINE:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text((check_ledger.ROOT / name).read_text(encoding='utf-8'), encoding='utf-8')
            self.assertEqual(check_ledger.outline_hash(), check_ledger.outline_hash(root))
            skill = root / 'SKILL.md'
            skill.write_text(skill.read_text(encoding='utf-8').replace('P1 证据', 'P1 证据改'), encoding='utf-8')
            self.assertNotEqual(check_ledger.outline_hash(), check_ledger.outline_hash(root))

    def test_real_ledger_outline_is_approved(self):
        text = check_ledger.LEDGER.read_text(encoding='utf-8')
        self.assertEqual([], check_ledger.check_outline(text))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'l.md'
            good = GOOD + '\n## Outline approval\n\n- Approved: user:2026-10-23\n- Outline: %s\n' % check_ledger.outline_hash()
            p.write_text(good, encoding='utf-8')
            self.assertEqual(0, check_ledger.main([str(p)]))
            p.write_text(good.replace('- Changed: SKILL.md, scripts/render_design_report.py', ''), encoding='utf-8')
            self.assertEqual(1, check_ledger.main([str(p)]))
            p.write_text(GOOD, encoding='utf-8')
            self.assertEqual(1, check_ledger.main([str(p)]))
            self.assertEqual(0, check_ledger.main(['--outline-hash']))


if __name__ == '__main__':
    unittest.main()
