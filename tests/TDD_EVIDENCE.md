# Builder TDD receipt

These are observations from the builder's actual terminal runs, not hypothetical output.
Commands below ran from this checkout on Python 3.12.13/macOS. Production behavior was
added vertically through the CLI, then checked through the library and installed artifact.
The initial `uv lock && uv run --extra dev pytest tests/test_snapshot.py -q` stopped at
editable-build setup because `src` did not yet exist; that is not counted as RED.

| Slice | Actual RED command and observation | Subsequent actual GREEN command and observation |
| --- | --- | --- |
| Snapshot CLI | `uv run --extra dev pytest tests/test_snapshot.py -q`: exit 1, missing executable package surface, 1 failed | `uv run --extra dev pytest -q`: exit 0, 1 passed; `uv run reruncheck snapshot src/reruncheck`: exit 0 |
| Bounded observations and explicit exclusions | `uv run --extra dev pytest tests/test_limits.py -q`: exit 1, 8 failed | `uv run --extra dev pytest -q`: exit 0, 9 passed; CLI max-bytes failure emitted one error object and exited 2 |
| Compare surface | `uv run --extra dev pytest tests/test_compare.py -q --tb=short`: exit 1, 9 failed | `uv run --extra dev pytest -q`: exit 0, 18 passed |
| Strict snapshot imports | `uv run --extra dev pytest tests/test_import.py -q --tb=short -k 'not fifo'`: exit 1, 21 failed/3 passed/1 deselected; FIFO-only run: exit 1, timed out after 10 seconds | `uv run --extra dev pytest -q --tb=short`: exit 0, 43 passed |
| Refuse implicit execution | `uv run --extra dev pytest tests/test_check.py -q --tb=short`: exit 1, 3 failed, missing check fields | `uv run --extra dev pytest -q`: exit 0, 46 passed |
| Two actual runs, observed effects, output counts | `uv run --extra dev pytest tests/test_check.py -q --tb=short -k observes`: exit 1, 2 failed | `uv run --extra dev pytest -q --tb=short`: exit 0, 48 passed |
| Expected first state independent of convergence | `uv run --extra dev pytest tests/test_check.py -q --tb=short -k expected`: exit 1, 4 failed | `uv run --extra dev pytest -q`: exit 0, 52 passed |
| Process and traversal failures retained together | `uv run --extra dev pytest tests/test_failures.py -q --tb=short`: exit 1, 3 failed/8 passed | `uv run --extra dev pytest -q`: exit 0, 63 passed |
| Copy/link/ignored-input preflight | `uv run --extra dev pytest tests/test_copy_safety.py -q --tb=short`: exit 1, 5 failed/2 passed | `uv run --extra dev pytest -q --tb=short`: exit 0, 70 passed |
| Interrupt receipt and cleanup | `uv run --extra dev pytest tests/test_lifecycle.py -q --tb=short`: exit 1, 1 failed/6 passed; CLI died with signal rather than reporting interruption | `uv run --extra dev pytest -q --tb=short`: exit 0, 77 passed |
| Packaged demo/human errors | `uv run --extra dev pytest tests/test_demo.py -q --tb=short`: exit 1, 3 failed | `uv run --extra dev pytest -q`: exit 0, 80 passed; actual stable demo exit 0 and broken demo exit 1 |
| Root mode observation | `uv run --extra dev pytest tests/test_root_mode.py -q --tb=short`: exit 1, 1 failed, false convergence | `uv run --extra dev pytest -q --tb=short`: exit 0, 81 passed |
| Literal argv, argument secrecy, report environment/budgets, safe path roundtrip | `uv run --extra dev pytest tests/test_semantics.py -q --tb=short`: exit 1, 5 failed | `uv run --extra dev pytest -q --tb=short`: exit 0, 94 passed after correcting a pytest temporary-parent setup error |
| Cleanup cannot retain success; root traversal race | `uv run --extra dev pytest tests/test_races.py -q --tb=short`: exit 1, 2 failed/1 passed | `uv run --extra dev pytest -q --tb=short`: exit 0, 97 passed |
| Bounded report preserves command receipts; human expected diff; unused options rejected | `uv run --extra dev pytest tests/test_reporting.py -q --tb=short`: exit 1, 3 failed | `uv run --extra dev pytest -q --tb=short`: exit 0, 100 passed |
| Relative link leaves and reenters original by name | `uv run --extra dev pytest tests/test_copy_safety.py -q --tb=short -k reenters`: exit 1, 1 failed | `uv run --extra dev pytest -q --tb=short`: exit 0, 101 passed |
| Directory alias hides an intermediate link escape | `uv run --extra dev pytest tests/test_copy_safety.py -q --tb=short -k alias_cannot`: exit 1, 1 failed | `uv run --extra dev pytest -q --tb=short`: exit 0, 102 passed |

A compare expectation was corrected during GREEN: replacing a default-mode regular file
with a directory changes both kind and mode; the test now requires both reasons rather
than suppressing a valid mode difference. No assertion was removed to make that case green.

Additional verification tests (not claimed as new RED cycles) cover exact/aggregate budgets,
missing expected state before launch, a successful second command followed by an unsupported
FIFO observation, external link contents never read, relative script resolution, and generated
simulations. The generated test ran with `uv run --extra dev pytest tests/test_simulations.py -q -s`:
8 passed, seeds 20261117 through 20261124, each with 24 tree pairs and 3 of each operation
(equal/add/remove/content/mode/type/target/rename). Its oracle compares original raw model bytes,
not snapshots or implementation digests. Each seed observed all six change reasons. These are
finite simulations, not an exhaustive state-space claim.

The first Ruff run identified import ordering, an unused import, an explicit `check=False`
requirement and a dict-literal style issue. Those were corrected; tests then reported 107 passed
and `uv run --extra dev ruff check .` reported all checks passed. A build produced both wheel and
sdist. The final artifact gate is `tests/verify_wheel.py`, which installs the local wheel with
`--no-deps --no-index` into a fresh external temporary environment, runs the isolated installed
surface, then removes that environment. Publication and independent acceptance remain parent work.

Final frozen-source gate (all exit 0; `$SCRATCH` replaces the builder's local absolute
scratch path for publication, without changing the recorded results):
- `TMPDIR=$SCRATCH uv run --extra dev pytest -q`: 107 passed in 8.97s.
- `TMPDIR=$SCRATCH uv run --extra dev ruff check . && TMPDIR=$SCRATCH uv run --extra dev ruff format --check src tests`: all checks passed; 31 files already formatted.
- `TMPDIR=$SCRATCH uv run --extra dev python -m build`: wheel and sdist built successfully; wheel built from that sdist.
- `TMPDIR=$SCRATCH uv run --extra dev python tests/verify_wheel.py dist/reruncheck-0.1.0-py3-none-any.whl`: fresh installed package resolved under the temporary environment's site-packages; runtime requirements empty; help/snapshot/equal comparison/passing expected check/stable demo exited 0, difference comparison and broken demo exited 1, missing trust exited 2. JSON and human demos both exercised. Owned install environment and fixtures removed.

The final runs explicitly set TMPDIR to authorized scratch. The obsolete source-only pytest
basetemp bootstrap was removed after inspecting the sdist manifest; tests now use normal pytest
temporary handling, so the sdist does not depend on an omitted conftest file or a hard-coded home.

## Additional root-binding regression

A later deterministic parent probe swapped the selected fixture root to an owned
outside-directory symlink between the early root check and path resolution. Before
the fix, the tool observed `outside.txt` and incorrectly returned convergence/0.
`uv run --extra dev pytest tests/test_root_binding.py -q` reproduced this as one
failing assertion (actual exit 0 versus required error/2).

The fix preserves the selected absolute path for no-follow filesystem operations;
its resolved path is used only for temporary-directory containment checks. The same
regression then passed (1 passed), the original standalone probe returned error/2
before any command launch, and the complete suite reported 108 passed. Existing
copy/link/traversal tests plus the new regression reported 13 passed; Ruff and the
32-file format check passed. These are finite checks, not a hostile-code sandbox
or a claim that every possible filesystem race is prevented.
