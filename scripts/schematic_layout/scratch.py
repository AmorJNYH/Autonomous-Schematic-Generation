"""Where throwaway runs write, for any agent or person running ASG.

$ASG_WORK_DIR if set, else the system temp dir (which honours TMPDIR). Outputs must stay
outside the skill itself so runs never dirty the repository.
"""
import os
import tempfile
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]


def scratch_base():
    return Path(os.environ.get('ASG_WORK_DIR') or tempfile.gettempdir()).resolve()


def require_scratch(path):
    """Reject an output/cache path inside the skill; any other location is the caller's choice."""
    resolved = Path(path).resolve()
    if resolved.is_relative_to(SKILL_ROOT):
        raise ValueError('%s is inside the skill (%s); write runs to a scratch directory such as %s'
                         % (resolved, SKILL_ROOT, scratch_base()))
    return resolved
