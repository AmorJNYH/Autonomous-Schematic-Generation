"""Where throwaway runs write, for any agent or person running ASG.

$ASG_WORK_DIR if set, else the system temp dir (which honours TMPDIR).
"""
import os
import tempfile
from pathlib import Path



def scratch_base():
    return Path(os.environ.get('ASG_WORK_DIR') or tempfile.gettempdir()).resolve()

