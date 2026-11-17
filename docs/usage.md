# Usage and report contract

## The two assertions

`check` observes the same copied tree after two executions of the supplied argv.

- **Convergence:** state after run one equals state after run two.
- **Expected first result:** when `--expect DIR` is supplied, state after run one equals that directory's snapshot under the same comparison policy.

Both commands must finish successfully and both observations must complete. A stable but wrong result fails the optional expected-state assertion. If both properties differ, `first_run_mismatch` is the primary outcome while the observed `converged` value and both diff lists remain available.

Without `--expect`, `first_run_asserted` is false and `first_run_matches` is null. Errors keep a distinct outcome; null is not converted to false or a successful assertion.

## Commands

```sh
reruncheck snapshot ROOT [--ignore PATTERN] [--json]
reruncheck compare BEFORE.json AFTER.json [--json]
reruncheck check --fixture ROOT --trust-command [--expect DIR] [--json] -- COMMAND ARG...
reruncheck demo --case stable --json
reruncheck demo --case broken --json
```

`snapshot` always writes JSON. Keep redirected output outside ROOT. `compare` reads version-one snapshot objects strictly and does not execute a command. `check` requires the literal `--` boundary; arguments following it are passed unchanged, not evaluated by a shell. `demo` executes only the package's original normalizer fixture code.

## Defaults and bounds

The common options are `--max-entries` (10,000), `--max-bytes` (64 MiB), and `--max-json-bytes` (16 MiB). `check` also accepts `--timeout` (10 seconds per execution) and `--max-output-bytes` (1 MiB combined stdout/stderr). Invalid/non-finite budgets are errors. JSON budgets have an explicit minimum so an error receipt can still be represented.

Command output is counted and discarded, not printed or retained in the report. Exceeding the output budget terminates ordinary child execution and records an error. A timeout is not evidence that the command had no side effects before termination.

POSIX process-group cleanup reaps ordinary children; it does not contain deliberately detached daemons. Only execute trusted code. The child receives the present allowlisted environment names `PATH`, `HOME`, `LANG`, `LC_ALL`, `LC_CTYPE`, `TZ`, and `TMPDIR`; reports contain their names, not values. A forwarded HOME still permits a trusted process to access user files or credential stores. This is not credential isolation.

## Snapshot policy

Recorded: relative path, entry kind, permissions, regular-file size/SHA-256 and literal symlink target. Root directory mode is compared too; its change uses path `.`. Empty directories and dotfiles are included. File contents and symlink directories are not followed through links.

Regular-file contents are read twice through one no-follow descriptor and must agree in size and SHA-256. This detects same-tick content changes even when timestamps do not change. `--max-bytes` caps included file-content bytes per snapshot, not cumulative I/O; verification normally doubles content reads and is itself capped. It is not an atomic snapshot or a guarantee against a coordinated hostile writer.

Not recorded for comparison: timestamps, ownership, ACLs, xattrs and hardlink identity. Every snapshot includes explicit coverage. A timestamp-only rewrite can therefore converge under this policy; the result is not a claim that no filesystem metadata changed.

Execution preflight rejects absolute source symlinks, escaping relative links, cycles and excessive link chains—even when an ignore pattern would exclude them from measurement. Snapshot-only can record a link target without following it. Portable imported paths reject backslashes, NULs, drive-like first components, absolute/empty/dot/parent components and duplicate paths. Special files and traversal failures are errors, not omitted entries.

## Ignore semantics

Repeated `--ignore PATTERN` arguments use case-sensitive `fnmatch` against the complete relative POSIX path. In this matcher `*` can match `/`; it is not a gitignore parser. A matching directory excludes its entire subtree from measurement. The patterns and excluded roots remain visible in coverage.

The complete source fixture is still validated and bounded before execution, then copied without dereferencing links. Ignoring a path is not permission to execute an unsafe fixture or to call an incomplete traversal clean.

## JSON outcomes

Check/demo reports use `schema_version: 1` and these outcome values:

| Outcome | Exit | Interpretation |
|---|---:|---|
| `converged` | 0 | Complete repeated-run comparison passed; optional expected state passed too. |
| `nonconvergent` | 1 | Run two changed observed state. |
| `first_run_mismatch` | 1 | Expected first result did not match, regardless of convergence. |
| `error` | 2 | Input, execution, observation, cleanup or resource-limit failure. |

Compare uses `equal`/`different` (0/1), or `error` (2). Snapshots carry `type: snapshot` and structured entry/coverage fields, not a command-correctness verdict.

Reports expose `first_run_asserted`, nullable `first_run_matches`/`converged`, `commands`, `changes`, `expected_changes`, `errors`, `coverage`, `observations`, `limits` and forwarded environment names. Command receipts retain phase, actual return code, timeout/output-limit/interrupt flags and observed byte counts. Change reasons are `added`, `removed`, `kind`, `content`, `mode`, and `target`; one path can have multiple reasons.

An oversized report becomes an explicit `report_limit` error with `report_truncated: true`, not a clean result with silently dropped changes. A receipt does not prove remote/database effects, all possible inputs, or hostile-code confinement. See [SECURITY.md](../SECURITY.md).
