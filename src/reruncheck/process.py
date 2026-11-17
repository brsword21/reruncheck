"""POSIX process execution with counted, discarded streams and group cleanup."""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    phase: str
    returncode: int | None
    timed_out: bool
    output_limited: bool
    stdout_bytes: int
    stderr_bytes: int
    duration_seconds: float
    interrupted: bool = False


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def execute(argv, cwd, env, limits, phase):
    started = time.monotonic()
    counts = {"stdout": 0, "stderr": 0}
    timed_out = limited = interrupted = False
    process = subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            for name, stream in [("stdout", process.stdout), ("stderr", process.stderr)]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                remaining = limits.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in selector.select(min(remaining, 0.05)):
                    chunk = os.read(
                        key.fd, min(65536, limits.max_output_bytes - sum(counts.values()) + 1)
                    )
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        counts[key.data] += len(chunk)
                        if sum(counts.values()) > limits.max_output_bytes:
                            limited = True
                            break
                if limited:
                    break
    except KeyboardInterrupt:
        interrupted = True
    finally:
        kill_group(process)
        process.wait()
        process.stdout.close()
        process.stderr.close()
    return CommandResult(
        phase,
        process.returncode,
        timed_out,
        limited,
        counts["stdout"],
        counts["stderr"],
        time.monotonic() - started,
        interrupted,
    )
