"""Local artifact gate: create/remove a fresh environment outside the checkout."""

import argparse
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "reruncheck/resources/normalizer.py" in names
        assert not any(name.endswith(".pyc") for name in names)
    smoke = Path(__file__).with_name("test_installed_smoke.py").resolve()
    with tempfile.TemporaryDirectory(prefix="reruncheck-wheel-", dir=os.environ["TMPDIR"]) as temp:
        root = Path(temp)
        python = root / "venv" / "bin" / "python"
        commands = [
            ["uv", "venv", str(root / "venv"), "--python", sys.executable],
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            [str(python), "-I", str(smoke)],
        ]
        for command in commands:
            result = subprocess.run(
                command, cwd=root, check=False, capture_output=True, text=True, timeout=60
            )
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            assert result.returncode == 0, (command, result.returncode)
    print("Fresh wheel environment and owned fixtures removed.")


if __name__ == "__main__":
    main()
