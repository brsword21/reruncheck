# Architecture

Reruncheck has one purpose: observe whether a selected filesystem result has converged under repeated execution of an explicitly trusted command.

```text
source fixture ── copy ── disposable working tree
                              │
                         snapshot before
                              │
                        trusted argv #1
                              │
                         snapshot first ───── expected tree (optional)
                              │                       │
                        trusted argv #2          first-state diff
                              │
                         snapshot second
                              │
                          state diff
                              │
                 typed outcome ── human / JSON
```

## Boundaries

Snapshotting, diffing, process execution and presentation remain separate concerns. The snapshot layer reports observed entries and explicit coverage; it does not normalize away unrecognized state. The diff layer compares path/kind/content/mode/link-target facts, rather than guessing behavior from logs. The runner owns its temporary copy and ordinary process lifecycle. The presentation layer derives output and exit status from the same result.

The runtime uses the Python standard library and does not call models, fetch schemas, install tools or discover arbitrary command text. JSON is a data contract; machine decisions use explicit enums, numbers and booleans/null—not regex over an LLM or command's prose.

## Content stability while reading

Nanosecond timestamp fields do not guarantee nanosecond filesystem precision; separate writes can share an inode timestamp.[14][15] Metadata checks alone therefore cannot establish that a digest came from unchanged content.

Each regular file is read twice through the same no-follow descriptor with unbuffered reads. The verification pass must match the first digest and size, while descriptor/path metadata checks still apply. Its byte count is capped at the first size plus one detection byte, so growth cannot create an unbounded verification read. `max_bytes` limits included regular-file bytes counted once per path per snapshot, not total I/O; normal verification doubles content-read I/O. This is bounded change detection, not an atomic filesystem snapshot or protection against a hostile writer coordinating mutations across both passes.

## Deliberate omissions

No database/network observer, daemon, dependency-injection framework, workflow graph, plugin protocol or automatic retry loop. No claim that content equality establishes semantic correctness or external-effect idempotence. No OS sandbox: a process's working directory is an observation scope, not a permission boundary.

## Verification

Tests must compare real synthetic tree changes against expected changes, include first-run-wrong and observation-error cases, and exercise actual bounded subprocesses. Packaging tests run the installed command outside the checkout. Separate review reruns verification rather than accepting the builder's summary. The release receipt names which checks actually ran; a CI template is not a successful CI run.

The accepted public contract is [SPEC.md](../SPEC.md). Names and interfaces in this overview are conceptual; the versioned CLI/report contract and actual package source are the implementation reference.

## Sources

[14] https://docs.kernel.org/filesystems/multigrain-ts.html
[15] https://docs.python.org/3/library/os.html
