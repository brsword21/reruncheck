"""Command line interface. JSON errors and successes each occupy one object."""

import argparse
import json
import sys

from .diff import compare
from .limits import Limits, ReruncheckError
from .report import CheckReport, Error
from .snapshot import load_snapshot, snapshot


class Parser(argparse.ArgumentParser):
    def error(self, message):
        if message.startswith("unrecognized arguments:"):
            message = "unrecognized arguments; check requires command argv after --"
        raise ReruncheckError(message)


def add_budgets(parser, *, allow_ignore=True):
    parser.add_argument("--max-entries", type=int, default=10_000)
    parser.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--max-json-bytes", type=int, default=16 * 1024 * 1024)
    if allow_ignore:
        parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--json", action="store_true")


def limited_report(report, limits):
    """Retain execution receipts, but explicitly refuse an oversized effect report."""
    reduced = {
        key: value
        for key, value in report.items()
        if key not in ("observations", "coverage", "entries", "root_mode", "type")
    }
    reduced.update(
        outcome="error",
        converged=None,
        changes=[],
        expected_changes=[],
        observations={},
        coverage={},
        report_truncated=True,
    )
    reduced["errors"] = [
        {
            "phase": error["phase"][:64],
            "code": error["code"][:64],
            "message": error["message"][:128],
        }
        for error in report.get("errors", [])[:3]
    ] + [
        {
            "phase": "report",
            "code": "report_limit",
            "message": "max_json_bytes exceeded; observations, coverage and changes omitted",
        }
    ]
    payload = json.dumps(reduced, sort_keys=True)
    if len(payload.encode()) + 1 > limits.max_json_bytes:
        reduced = {
            "schema_version": 1,
            "outcome": "error",
            "report_truncated": True,
            "commands": report.get("commands", []),
            "converged": None,
            "first_run_asserted": report.get("first_run_asserted", False),
            "first_run_matches": report.get("first_run_matches"),
            "changes": [],
            "expected_changes": [],
            "coverage": {},
            "errors": [reduced["errors"][-1]],
        }
        payload = json.dumps(reduced, sort_keys=True)
    return reduced, payload


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    phase = argv[0] if argv else "usage"
    options = argv[: argv.index("--")] if phase == "check" and "--" in argv else argv
    json_mode = "--json" in options or phase == "snapshot"
    try:
        parser = Parser(prog="reruncheck")
        commands = parser.add_subparsers(dest="command", required=True)
        snap = commands.add_parser("snapshot")
        snap.add_argument("root")
        add_budgets(snap)
        comp = commands.add_parser("compare")
        comp.add_argument("before")
        comp.add_argument("after")
        add_budgets(comp, allow_ignore=False)
        run = commands.add_parser("check")
        run.add_argument("--fixture", required=True)
        run.add_argument("--expect")
        run.add_argument("--trust-command", action="store_true")
        run.add_argument("--timeout", type=float, default=10.0)
        run.add_argument("--max-output-bytes", type=int, default=1024 * 1024)
        add_budgets(run)
        demo_parser = commands.add_parser("demo")
        demo_parser.add_argument("--case", choices=["stable", "broken"], default="stable")
        add_budgets(demo_parser, allow_ignore=False)
        command_argv = []
        if phase == "check" and "--" in argv:
            separator = argv.index("--")
            command_argv, argv = argv[separator + 1 :], argv[:separator]
        args = parser.parse_args(argv)
        limits = Limits(
            max_entries=args.max_entries,
            max_bytes=args.max_bytes,
            max_json_bytes=args.max_json_bytes,
            timeout=getattr(args, "timeout", 10.0),
            max_output_bytes=getattr(args, "max_output_bytes", 1024 * 1024),
        )
        exit_code = 0
        if args.command == "snapshot":
            report = snapshot(args.root, ignores=args.ignore, limits=limits).to_dict()
        elif args.command == "check":
            from .runner import check

            checked = check(
                args.fixture,
                command_argv,
                trust_command=args.trust_command,
                expect=args.expect,
                ignores=args.ignore,
                limits=limits,
            )
            report, exit_code = checked.to_dict(), checked.exit_code
        elif args.command == "demo":
            from .demo import demo

            checked = demo(args.case, limits=limits)
            report, exit_code = checked.to_dict(), checked.exit_code
        else:
            before = load_snapshot(args.before, limits=limits)
            after = load_snapshot(args.after, limits=limits)
            changes = compare(before, after)
            report = {
                "schema_version": 1,
                "outcome": "different" if changes else "equal",
                "changes": [change.to_dict() for change in changes],
                "coverage": {"before": before.coverage, "after": after.coverage},
                "errors": [],
            }
            exit_code = int(bool(changes))
        payload = json.dumps(report, sort_keys=True)
        if len(payload.encode()) + 1 > limits.max_json_bytes:
            report, payload = limited_report(report, limits)
            exit_code = 2
        if json_mode:
            print(payload)
        else:
            output = sys.stderr if exit_code == 2 else sys.stdout
            print(report["outcome"], file=output)
            if "first_run_asserted" in report:
                for field in ("first_run_asserted", "first_run_matches", "converged"):
                    print(f"{field}: {json.dumps(report[field])}", file=output)
                print(report["correctness_scope"], file=output)
                print(report["execution_boundary"], file=output)
            for change in report["changes"]:
                print(f"{change['path']}: {', '.join(change['reasons'])}", file=output)
            for change in report.get("expected_changes", []):
                print(f"expected {change['path']}: {', '.join(change['reasons'])}", file=output)
            for error in report.get("errors", []):
                print(f"{error['phase']}: {error['code']}: {error['message']}", file=output)
        return exit_code
    except (OSError, ValueError, RecursionError) as exc:
        report = {
            "schema_version": 1,
            "outcome": "error",
            "errors": [{"phase": phase, "code": type(exc).__name__, "message": str(exc)[:256]}],
        }
        if phase in ("check", "demo"):
            check_report = CheckReport()
            check_report.errors.append(Error(phase, type(exc).__name__, str(exc)[:256]))
            report = check_report.to_dict()
        if json_mode:
            print(json.dumps(report, sort_keys=True))
        else:
            print(f"{phase}: {exc}", file=sys.stderr)
        return 2
