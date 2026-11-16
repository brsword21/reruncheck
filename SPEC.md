# Reruncheck — SPEC

Status: implementation contract for v0.1.0. Chosen 2026-11-17 after bounded recent-month GitHub research and explicit prior-art counter-search. License: Apache-2.0. Original implementation; no copied upstream implementation, fixtures, logos or proprietary data.

## 1. Problem and intentional boundary

A command can return zero twice while the second run renames files again, appends duplicate content, changes modes or removes an already-correct output. Code generators, exporters, local migrations and cleanup scripts need observable filesystem convergence tests, not a command's self-reported change count.

Reruncheck snapshots an explicitly selected fixture tree, executes an explicitly trusted command twice on a disposable copy, and compares observed states. It can assert an expected first-run tree too, so a stable but wrong output is distinguishable from a correct converged result.

This is **not a sandbox**, a universal correctness proof, an agent, a filesystem monitor, a cloud service, a security scanner or a substitute for tests of database/network side effects. No command runs by discovery. Only user-supplied trusted commands explicitly opted into execution may run; default standalone snapshot/compare operations are read-only. Commands can affect resources outside cwd. A temporary directory and a sanitized environment do not establish confinement.

## 2. Users and jobs

- Maintainer of a generator: make repeated generation a CI assertion without trusting the generator's logs.
- Author of a migration/export/rename script: find second-run file/path/content/type/mode changes with a short synthetic fixture.
- Contributor reporting a bug: attach a deterministic JSON effect receipt, not a private working tree.

Success is a short, runnable clean/dirty example and a trustworthy diff. Stars and adoption are not release gates or promised outcomes.

## 3. Research and novelty boundary

The research survey covers 15 purposively selected recent-month breakout repositories plus issue/source studies; provider-labelled daily additions and monthly panels are not silently called exact UTC net growth. Attention to audit/review/quality tools motivates a tiny independent verification primitive, not a claim of product demand. See docs/research.md and the original research dossier.

Closest prior art: Molecule already reruns convergence and checks Ansible's change reporting; generic shell tests and directory diff cover simple cases. MCP Behavior already validates tool responses and effects; schema diff/lockfile/VCR tools were rejected as duplicate product ideas. A discovered project named Twicerun checks batch-pipeline repeatability, so that working name was rejected. Reruncheck earns its scope with command-independent filesystem snapshots, first-result assertions, explicit comparison coverage, bounded execution and a credential-free installed demo. No universal novelty claim.

## 4. Distribution and architecture

- Python >=3.10, standard library only at runtime. Package `reruncheck`, command `reruncheck`, src layout.
- Linux and macOS POSIX execution supported. Snapshot/compare serialization is portable; do not claim Windows execution support without actual tests.
- Tiny composable modules: snapshot, diff, runner, report/CLI; avoid a plug-in system, YAML DSL, daemon or configuration hierarchy.
- Stable versioned JSON envelopes; dataclasses/enums internally are preferred over free-text status parsing. No LLM required, no network calls or provider SDKs in runtime.
- Dev tools may include pytest, Ruff and build. Project-scoped environment/lock only; no global configuration changes.

## 5. User surface

```sh
# Safe offline demo using only package-authored fixture code
reruncheck demo --case stable
reruncheck demo --case broken --json

# Explicit trusted execution: argv, not a shell string
reruncheck check --fixture ./fixtures/input --trust-command \
  --expect ./fixtures/expected -- python normalize.py

# Read-only operations; shell redirection is the caller's choice
reruncheck snapshot ./output > before.json
reruncheck compare before.json after.json --json
```

`check` runs argv directly with no `shell=True`, in a disposable copied tree, twice sequentially. It never changes the source fixture through its own copy/snapshot logic; that is not a guarantee about arbitrary executed commands. Require a nonempty argv and `--trust-command` before spawning anything. `--expect` is a directory containing the expected first-run tree (same snapshot policy); absence must produce `first_run_asserted: false`, never an assertion of first-run correctness. Optional `--ignore` is explicit and reported; never silently ignore hidden files or failures. `--timeout` and other budgets are positive bounded values with actionable invalid-input errors.

The original fixture may contain a command script, but executable resolution is caller responsibility: relative script paths resolve in the copied working tree. Absolute script paths execute the explicitly named script outside the fixture, with the same trust boundary. Never auto-expand shell syntax, `~`, variables or glob patterns in argv.

Default command environment should be predictable and must not copy all credential variables into reports. Document exactly which environment is forwarded. Preserving ordinary command execution semantics is more important than pretending environment filtering makes a sandbox. No raw environment values, source contents, stdout/stderr or full secret-bearing argv in JSON reports by default. Captured output counts and optional narrowly bounded opt-in diagnostics are allowed; filenames/link targets may themselves be sensitive and this limitation must be documented.

## 6. Snapshot contract

Snapshot exact relative paths without following symlink directories or symlink file contents. Each supported entry records kind (`file`, `directory`, `symlink`), stable relevant permissions/mode, file size and SHA-256 for regular files, and literal symlink target for links. Include empty directories and dotfiles. Sort paths deterministically. Distinguish removal/addition, content change, kind change, mode change and changed link target; one item may have several reasons.

Not compared by default: mtime/atime/ctime, uid/gid, ACLs, xattrs and hardlink identity. Name them in comparison coverage. Timestamp-only churn must not be misrepresented as a captured change. Explicit ignore patterns must be recorded along with enough coverage information to know the test excludes paths.

Fail loudly on unreadable entries, traversal races that invalidate a digest, unsupported special files (FIFO/socket/device), over-budget trees and invalid serialized snapshots. Never label an incomplete traversal clean. Hash in chunks with a byte budget, not one unbounded read. Bound entry count, total bytes, snapshot JSON file size, report/output capture and execution time. Reject duplicate/unsafe relative paths and structurally malformed snapshots on import. Preserve JSON types; do not coerce arbitrary strings to booleans/numbers.

Source fixture symlinks must be copied as links, never dereferenced into unrelated host data; reject source symlinks that escape the selected fixture for check execution, or document/require an explicit stronger opt-in. Snapshot-only can record any link target safely without dereferencing. Directory exclusion semantics must be clear and consistent across all snapshots.

## 7. Execution and lifecycle

- Preflight fixture/expected paths, trust flag, argv and budgets before command launch. Prepare disposable copy outside the source tree. Runner artifacts/logs live outside the measured tree.
- Capture original state, run one, snapshot one, run two, snapshot two. State comparison is after run one versus after run two; expected-state comparison is expected versus after run one.
- Record actual command return codes, timeouts, bounded output-byte accounting and phase-specific errors as structured values. Never parse success or changed counts from prose.
- On command failure, timeout, output limit or traversal failure, report an error/incomplete outcome, never convergence. On POSIX create and terminate the child process group for ordinary child cleanup. Do not claim containment of hostile or deliberately detached descendants.
- Bound stdout/stderr consumption while the process runs; avoid `communicate()` with unbounded buffers and unbounded log files. Reap processes, close streams/threads and remove owned temporary resources, including on Ctrl-C or exceptions.
- No automatic retries of commands: they may have side effects. No ambient credential lookup or downloads.

## 8. Outcome/report contract

Every CLI command supports machine-readable JSON where meaningful. Human and JSON results derive from the same typed result; JSON stdout contains one valid object and no progress chatter. Human errors go to stderr unless the selected JSON envelope carries them.

Minimum check report fields: schema_version, outcome enum, first_run_asserted, first_run_matches (nullable), converged (nullable), comparison coverage/exclusions, phase/command results, changes, expected-state changes, and structured errors. Distinguish `converged` from `nonconvergent`, `first_run_mismatch`, and `error`; false/null are not interchangeable. Timing fields may vary; path/diff order must not.

Exit codes:
- 0: the requested comparison completed and passed (for check: both commands successful, state converged, optional expected state matches).
- 1: observed state difference or expected first-run mismatch.
- 2: invalid input, unavailable/unsupported operation, incomplete observation, command failure, timeout or resource-budget failure.

Exit 0 without --expect proves only convergence under the recorded filesystem comparison, not correctness. Reports explicitly say so. CLI usage examples and installed demo must demonstrate all three statuses. An intentionally failing demo exits 1; do not hide that to make a demo command look green.

## 9. Original demo

Stable case: normalize a synthetic text file (CRLF to LF, one consistent value). Run one creates the expected normalized content; run two may rewrite timestamps but content/path/mode state is unchanged. First-run assertion enabled.

Broken case: an authored normalizer/renamer makes a further content or name change every invocation. Both command return codes are zero; state diff must show nonconvergence. Use no actual upstream bug/code/private fixtures. Show exactly why success codes are insufficient. No screenshot or fake terminal output substituted for a real run.

## 10. Acceptance gates

A. Install/build: `uv run --extra dev python -m build` produces a wheel and sdist. Install the wheel into a fresh environment outside the source tree; `reruncheck --help`, `snapshot`, `compare`, passing check and both demo variants work there without source-tree imports or runtime dependencies.

B. Deterministic functional tests: baseline-equal snapshots; added/removed/empty/hidden entries; content/mode/type/link changes; stable wrong first run; expected state pass; first/second command failure; missing trust/argv; no shell expansion; invalid JSON/paths/duplicate entries; ignore accounting; missing input; over-budget data and unsupported file types.

C. Adversarial POSIX execution: timeout and ordinary child termination; stdout/stderr flood with bounded capture; symlink escape refusal/no symlink dereference; fixture remains byte-identical under package-authored demo commands; resources cleaned on success and error. Never execute an untrusted external repository.

D. Meaningful generated simulations: original synthetic tree mutations checked against an independently simple expected-diff oracle, deterministic seed, meaningful path/mode/type cases. Report actual observed counts/limits, not 'coverage' inferred from random iteration counts.

E. Quality: `uv run --extra dev pytest -q` and `uv run --extra dev ruff check .`; separate reviewer reruns tests and installed demo, inspects process/file safety and misleading success conditions. No skipping or weakening tests to pass. Record RED -> GREEN for vertical features.

F. Product/docs: English README with real usage and limitations, short architecture, API/report description, security/trust policy, contribution guide, changelog, Apache-2.0 LICENSE/NOTICE, original runnable demo, reproducible test/build instructions, no fabricated badges/benchmarks/adoption claims. Dependency license audit before publication.

G. Publication: new public `brsword21/reruncheck`, exact committed code and Apache-2.0 recognized by GitHub; versioned release with built artifacts and checksums, verified with fresh remote reads and a clean clone. Attempt GitHub Actions when credentials allow; if workflow scope is refused, do not bypass it, publish the CI template and honest local/independent test receipt, disclose hosted CI as not observed. No PyPI/npm release, promo posts or existing-repo changes authorized.

## 11. Build order and ownership

1. Parent: this SPEC, research synthesis/decision, independent acceptance expectations, license/docs. Bootstrap only; no production-code stub.
2. One native Hermes builder: `src/**`, `tests/**`, `pyproject.toml`, `uv.lock`; strict TDD with real RED/GREEN evidence and installed surface checks. Builder may add packaged resources under src. No changes to SPEC, parent docs, private control/recovery or other projects; no remote publication. Parent inheritance gpt-6.1-sol intentionally used for the tested subscription route.
3. Parent integrates and exercises result, supplies docs and build artifacts; then independent read-only reviewer may add only a separate review report outside the repo (and proposed tests as requested, not edit existing checks).
4. Parent fixes verified findings through new failing tests, reruns gates, publishes and reads remote state back.

No competing writers on core files. This is an unscored feature project, not an invented numeric quality optimization. Freeze this acceptance contract before implementation; narrower explicit support is allowed only if recorded honestly and does not turn a required failure into success.

## 12. Definition of done / stop

Done means the original demo and credible command-check workflow really run from the installed artifact, acceptance results/reviewer exist, docs match behavior, and public GitHub/release/license have verified handles. A speculative market gap, a stub, dispatch, plan, green self-written tests alone or a code review summary does not meet the gate. Stop by 2026-11-23T23:58:25+01:00 and report remaining work if incomplete. Continue from the private project checkpoint after quota interruption; no spending or policy bypass to recover.
