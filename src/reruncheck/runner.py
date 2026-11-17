"""Explicit trusted two-run checks. A disposable copy is not a sandbox."""

import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .copying import copy_fixture, validate_links
from .diff import compare
from .limits import Limits, ReruncheckError
from .process import execute
from .report import CheckReport, Error, Outcome
from .snapshot import snapshot

# Deliberately narrow inheritance. No credentials or caller Python startup flags.
FORWARDED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR")


def check(fixture, argv, *, trust_command=False, expect=None, ignores=(), limits=None):
    report = CheckReport(first_run_asserted=expect is not None)
    phase = "preflight"
    try:
        limits = limits or Limits()
        report.limits = asdict(limits)
        if trust_command is not True:
            raise ReruncheckError("check requires explicit --trust-command")
        if (
            type(argv) not in (list, tuple)
            or not argv
            or not argv[0]
            or any(type(arg) is not str or "\0" in arg for arg in argv)
        ):
            raise ReruncheckError("command must be a nonempty argv after --")
        if os.name != "posix":
            raise ReruncheckError("command execution requires POSIX")
        fixture = Path(fixture)
        expected = snapshot(expect, ignores=ignores, limits=limits) if expect is not None else None
        if expected is not None:
            report.coverage["expected"] = expected.coverage
            report.observations["expected"] = expected.to_dict()
        # Reject a symlink root before canonicalizing its parent path.
        if fixture.is_symlink():
            raise ReruncheckError("fixture root must not be a symlink")
        # Preserve the selected final component for no-follow I/O. Using its
        # resolved target would accept a root swapped to an outside symlink.
        fixture = fixture.absolute()
        resolved_fixture = fixture.resolve()
        temp_base = Path(tempfile.gettempdir()).resolve()
        if temp_base.is_relative_to(resolved_fixture) or (
            expect is not None and temp_base.is_relative_to(Path(expect).resolve())
        ):
            raise ReruncheckError("temporary directory must be outside fixture/expected tree")
        inventory = snapshot(fixture, limits=limits)
        validate_links(inventory)
        original = snapshot(fixture, ignores=ignores, limits=limits)
        report.coverage["original"] = original.coverage
        report.observations["original"] = original.to_dict()
        env = {key: os.environ[key] for key in FORWARDED_ENV if key in os.environ}
        report.environment_forwarded = sorted(env)
        with tempfile.TemporaryDirectory(prefix="reruncheck-") as temporary:
            work = Path(temporary) / "tree"
            phase = "copy"
            copy_fixture(fixture, work, inventory, limits)
            if compare(inventory, snapshot(work, limits=limits)) or compare(
                inventory, snapshot(fixture, limits=limits)
            ):
                raise ReruncheckError("fixture changed or disposable copy differs")
            states = []
            for number, name in [(1, "first"), (2, "second")]:
                phase = f"run_{name}"
                result = execute(argv, work, env, limits, phase)
                report.commands.append(result)
                if result.interrupted:
                    report.errors.append(Error(phase, "interrupted", "command interrupted"))
                if result.timed_out:
                    report.errors.append(Error(phase, "timeout", "command timeout exceeded"))
                if result.output_limited:
                    report.errors.append(Error(phase, "output_limit", "max_output_bytes exceeded"))
                if result.returncode and not (
                    result.timed_out or result.output_limited or result.interrupted
                ):
                    report.errors.append(
                        Error(phase, "nonzero_exit", f"command exited {result.returncode}")
                    )
                phase = f"after_{name}"
                state = snapshot(work, ignores=ignores, limits=limits)
                states.append(state)
                report.observations[phase] = state.to_dict()
                report.coverage[phase] = state.coverage
                if report.errors:
                    phase = "cleanup"
                    return report
                if number == 1 and expected is not None:
                    expected_changes = compare(expected, state)
                    report.expected_changes = [change.to_dict() for change in expected_changes]
                    report.first_run_matches = not expected_changes
            changes = compare(*states)
            report.changes = [change.to_dict() for change in changes]
            report.converged = not changes
            report.outcome = Outcome.NONCONVERGENT if changes else Outcome.CONVERGED
            if report.first_run_matches is False:
                report.outcome = Outcome.FIRST_RUN_MISMATCH
            phase = "cleanup"
    except KeyboardInterrupt:
        report.outcome = Outcome.ERROR
        report.errors.append(Error(phase, "interrupted", "operation interrupted"))
    except (OSError, ValueError, RecursionError) as exc:
        report.outcome = Outcome.ERROR
        report.errors.append(Error(phase, type(exc).__name__, str(exc)))
    return report
