import json
import sys

from test_snapshot import cli


def test_root_directory_mode_churn_is_not_false_convergence(tmp_path):
    script = (
        "import os,stat; mode=stat.S_IMODE(os.stat('.').st_mode); "
        "os.chmod('.', 0o700 if mode != 0o700 else 0o755)"
    )
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == 1, result.stdout
    doc = json.loads(result.stdout)
    assert doc["changes"] == [{"path": ".", "reasons": ["mode"]}]
    assert doc["converged"] is False
