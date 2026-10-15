"""Scratch outputs work for any runner and never land inside the skill."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.scratch import SKILL_ROOT, require_scratch, scratch_base


class ScratchTests(unittest.TestCase):
    def test_any_location_outside_the_skill_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(require_scratch(Path(tmp) / 'out'), (Path(tmp) / 'out').resolve())

    def test_inside_the_skill_is_rejected(self):
        with self.assertRaises(ValueError):
            require_scratch(SKILL_ROOT / 'evals' / 'out')

    def test_base_follows_env_then_system_temp(self):
        with mock.patch.dict(os.environ, {'ASG_WORK_DIR': '/var/tmp'}):
            self.assertEqual(scratch_base(), Path('/var/tmp').resolve())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ASG_WORK_DIR', None)
            self.assertEqual(scratch_base(), Path(tempfile.gettempdir()).resolve())


if __name__ == '__main__':
    unittest.main()
