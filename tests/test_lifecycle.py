import json
import os
import signal
import subprocess
import sys
import time

import pytest
from test_snapshot import cli


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_flood_is_counted_discarded_and_bounded(tmp_path, stream):
    script = (
        f"import os; fd={1 if stream == 'stdout' else 2}; "
        "payload=b'SECRET_OUTPUT'*10000\nwhile True: os.write(fd,payload)"
    )
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        "--max-output-bytes",
        "1000",
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == 2
    doc = json.loads(result.stdout)
    assert doc["converged"] is None
    command = doc["commands"][0]
    assert command["output_limited"] is True
    assert command["stdout_bytes"] + command["stderr_bytes"] == 1001
    assert doc["errors"][0]["code"] == "output_limit"
    assert "SECRET_OUTPUT" not in result.stdout
    assert len(result.stdout) < 10000


def test_timeout_kills_ordinary_child_group(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    late = tmp_path / "late"
    child = f"import time; time.sleep(.7); open({str(late)!r},'w').close()"
    script = (
        f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "time.sleep(30)"
    )
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        "--timeout",
        ".2",
        "--",
        sys.executable,
        "-c",
        script,
    )
    doc = json.loads(result.stdout)
    assert result.returncode == 2
    assert doc["commands"][0]["timed_out"] is True
    assert doc["commands"][0]["duration_seconds"] < 2
    assert doc["errors"][0]["phase"] == "run_first"
    time.sleep(0.8)
    assert not late.exists()


@pytest.mark.parametrize("script", ["pass", "raise SystemExit(4)", "import time;time.sleep(9)"])
def test_owned_temporary_resources_are_removed(tmp_path, monkeypatch, script):
    import tempfile

    from reruncheck.limits import Limits
    from reruncheck.runner import check

    fixture, temporary = tmp_path / "fixture", tmp_path / "temps"
    fixture.mkdir()
    temporary.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporary))
    check(fixture, [sys.executable, "-c", script], trust_command=True, limits=Limits(timeout=0.1))
    assert list(temporary.iterdir()) == []


def test_interrupt_is_structured_and_reaps_child(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    marker = tmp_path / "started"
    script = f"import os,time; open({str(marker)!r},'w').write(str(os.getpid())); time.sleep(30)"
    command = [
        sys.executable,
        "-m",
        "reruncheck",
        "check",
        "--fixture",
        str(fixture),
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        script,
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists()
        child_pid = int(marker.read_text())
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=3)
        assert process.returncode == 2
        doc = json.loads(stdout)
        assert doc["outcome"] == "error"
        assert doc["errors"][-1]["code"] == "interrupted"
        assert doc["commands"][0]["returncode"] == -signal.SIGKILL
        assert doc["commands"][0]["interrupted"] is True
        assert "Traceback" not in stderr
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
