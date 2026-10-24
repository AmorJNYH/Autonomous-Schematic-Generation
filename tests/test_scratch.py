"""Scratch outputs go to $ASG_WORK_DIR or the system temp dir."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.scratch import scratch_base


class ScratchTests(unittest.TestCase):
    def test_base_follows_env_then_system_temp(self):
        with mock.patch.dict(os.environ, {'ASG_WORK_DIR': '/var/tmp'}):
            self.assertEqual(scratch_base(), Path('/var/tmp').resolve())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ASG_WORK_DIR', None)
            self.assertEqual(scratch_base(), Path(tempfile.gettempdir()).resolve())


if __name__ == '__main__':
    unittest.main()
