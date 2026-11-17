"""Run with a fresh wheel environment's Python -I, from outside the source tree."""

import json
import os
import subprocess
import sys
import tempfile
from importlib.metadata import distribution
from pathlib import Path


def main():
    import reruncheck

    installed = Path(reruncheck.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()), installed
    metadata = distribution("reruncheck")
    assert metadata.version == "0.1.0"
    runtime_requirements = [
        requirement for requirement in (metadata.requires or []) if "extra ==" not in requirement
    ]
    assert not runtime_requirements
    console = Path(sys.prefix) / "bin" / "reruncheck"
    receipts = []
    with tempfile.TemporaryDirectory(
        prefix="reruncheck-installed-", dir=os.environ["TMPDIR"]
    ) as temp:
        cwd = Path(temp)
        source, expected = cwd / "fixture", cwd / "expected"
        source.mkdir()
        expected.mkdir()
        (source / "data").write_bytes(b"value=one\r\n")
        (expected / "data").write_bytes(b"value=one\n")

        def run(name, args, code, outcome=None):
            result = subprocess.run(
                [str(console), *map(str, args)],
                cwd=cwd,
                check=False,
                text=True,
                capture_output=True,
                timeout=15,
            )
            assert result.returncode == code, (name, result.stdout, result.stderr)
            if outcome is not None:
                assert json.loads(result.stdout)["outcome"] == outcome, result.stdout
            receipts.append({"name": name, "exit_code": result.returncode})
            return result

        run("help", ["--help"], 0)
        before = cwd / "before.json"
        after = cwd / "after.json"
        before.write_text(run("snapshot", ["snapshot", source], 0).stdout)
        after.write_text(run("expected_snapshot", ["snapshot", expected], 0).stdout)
        run("compare_equal", ["compare", before, before, "--json"], 0, "equal")
        run("compare_difference", ["compare", before, after, "--json"], 1, "different")
        script = "from pathlib import Path; Path('data').write_bytes(b'value=one\\n')"
        checked = run(
            "passing_check",
            [
                "check",
                "--fixture",
                source,
                "--expect",
                expected,
                "--trust-command",
                "--json",
                "--",
                sys.executable,
                "-c",
                script,
            ],
            0,
            "converged",
        )
        assert json.loads(checked.stdout)["first_run_matches"] is True
        assert (source / "data").read_bytes() == b"value=one\r\n"
        run(
            "missing_trust",
            ["check", "--fixture", source, "--json", "--", sys.executable, "-c", "pass"],
            2,
            "error",
        )
        run("stable_demo", ["demo", "--case", "stable", "--json"], 0, "converged")
        run("broken_demo", ["demo", "--case", "broken", "--json"], 1, "nonconvergent")
        run("human_stable_demo", ["demo", "--case", "stable"], 0)
        run("human_broken_demo", ["demo", "--case", "broken"], 1)
    print(
        json.dumps(
            {
                "installed_package": str(installed),
                "runtime_requirements": runtime_requirements,
                "receipts": receipts,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
