# Reruncheck

**Test convergence, not exit codes.**

A generator succeeds. You run it again. It succeeds again—and quietly changes your files again.

Reruncheck runs a trusted command twice on a disposable copy of a fixture and compares the actual filesystem effects. Add an expected output tree to catch a first run that is stable but wrong.

- Observe content, names, file types, permissions and symlink targets—not a command's own change counter.
- Keep the original fixture untouched by Reruncheck's copy/snapshot operations.
- Use a readable diff locally and a versioned JSON receipt in CI.
- Run without an LLM, API key, network service or runtime dependency.

> **Not a sandbox.** Only run commands you trust. A copied working directory does not stop a command from accessing the rest of your machine, network or credentials. See [the trust model](SECURITY.md).

## See the failure in a minute

Python 3.10+; command execution currently targets Linux and macOS.

```sh
python -m pip install 'git+https://github.com/brsword21/reruncheck.git@v0.1.0'
reruncheck demo --case stable
reruncheck demo --case broken --json
```

The stable demo normalizes an original synthetic text fixture and then converges. The broken demo uses an intentionally non-idempotent command: both executions return zero, but the second changes the file again. It exits **1 on purpose**. These are authored examples, not claims to reproduce a third-party bug.

Selected fields from an actual broken-demo result (the full JSON also contains coverage, limits and observations):

```json
{
  "outcome": "nonconvergent",
  "commands": [
    {"phase": "run_first", "returncode": 0},
    {"phase": "run_second", "returncode": 0}
  ],
  "changes": [{"path": "data.txt", "reasons": ["content"]}]
}
```

## Check your generator or migration

```sh
reruncheck check \
  --fixture ./testdata/input \
  --expect ./testdata/expected \
  --trust-command \
  -- my-generator .
```

Replace `my-generator .` with your command and arguments. The command runs in a temporary copy of `./testdata/input`; relative paths in its argv resolve there. Put a relative script in the fixture, or explicitly pass an absolute script path. Reruncheck does not expand shell expressions, variables or wildcards.

`--expect` asserts the tree after the first run. Without it, a passing result establishes only **convergence under the stated comparison policy**, not correctness. Exclude intentionally changing generated files only through explicit, reported ignore patterns.

## Compare states without executing anything

```sh
reruncheck snapshot ./output > before.json
# Run your operation separately.
reruncheck snapshot ./output > after.json
reruncheck compare before.json after.json --json
```

Keep snapshot/report files outside the measured tree. Snapshot and compare do not launch a command. Symlinks are recorded, not followed; special or unreadable entries and exceeded budgets cannot produce a clean result.

## Exit codes you can rely on

| Code | Meaning |
|---|---|
| `0` | Observation completed and the requested assertion passed. |
| `1` | A state difference or expected-first-run mismatch was observed. |
| `2` | Invalid input, incomplete observation, command failure, timeout or resource limit. |

JSON mode emits a machine-readable result rather than parsing a command's prose. Human and JSON reports share the same underlying result. See [the specification](SPEC.md) for the outcome and coverage contract.

## What this does not prove

- No assertion about databases, remote APIs, network effects or paths outside the selected tree.
- No comparison of timestamps, ownership, ACLs, xattrs or hardlink identity by default.
- No protection from hostile commands or deliberately detached processes.
- No guarantee that a finite successful fixture covers all inputs.
- No privacy guarantee for reports: filenames and symlink targets can be sensitive, even when file contents and environment values are omitted.

## Development

```sh
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check .
uv run --extra dev python -m build
```

The runtime is standard-library-only. Development tools are separate. Tests cover real disposable trees and processes; the installed wheel and deliberately failing demo are checked separately. The exact release validation receipt is published with the release, not inferred from a badge.

Read [CONTRIBUTING.md](CONTRIBUTING.md), [architecture](docs/architecture.md), [research and prior art](docs/research.md), and [SPEC.md](SPEC.md).

## Why a separate tool?

Molecule already tests Ansible idempotence, and a shell script plus `diff` is enough for simple cases. Reruncheck is the small command-independent option when you want first-result assertions, filesystem-aware changes, explicit observation limits and a reusable CI receipt. It is not another agent framework or an automatic correctness score.

## License

[Apache-2.0](LICENSE). Original code and fixtures; see [NOTICE](NOTICE).
