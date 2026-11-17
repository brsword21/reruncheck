# Security and trust model

## Commands are trusted code

`check --trust-command -- ...` deliberately executes the supplied argv. The opt-in is not a security boundary. A process can access files outside its working directory, use available credentials, contact the network, create detached processes or modify system state under its user privileges.

Reruncheck is a test utility for commands you already trust—not a way to run an unfamiliar repository, a downloaded installer or hostile code safely. Use a separately configured VM/container/sandbox if you need confinement. Reruncheck never silently substitutes host execution for an unavailable sandbox, because it does not promise a sandbox in the first place.

## What the package owns

The package owns its temporary fixture copy, captured-process streams and result artifacts. Snapshot traversal does not intentionally follow symlinks or execute fixture content. Resource budgets bound supported observation and ordinary child execution. POSIX process-group termination is lifecycle cleanup, not containment of deliberately escaped daemons.

A command's two successful return codes do not prove unchanged files. Conversely, unchanged files do not prove that the command had no external side effects. A stable first result may still be wrong; use an expected-state assertion where appropriate.

## Sensitive data

Reports omit source file contents, raw environment values and command stdout/stderr by default. They can still reveal filenames, relative paths, link targets, content digests, entry sizes and process diagnostics. Treat reports from private fixtures as potentially sensitive. Do not paste credentials into command arguments or publish receipts containing private identifiers.

No runtime telemetry, automatic source upload, hosted model or credential lookup is part of the intended package contract. Review opt-in diagnostics before sharing them. No claim of anonymization or cryptographic attestation is made.

## Input and failure policy

Malformed snapshots, unsafe imported paths, unsupported file types, unreadable entries, traversal inconsistencies, command failures, timeouts and exceeded limits are errors—not empty/equal snapshots. Comparison coverage and intentional exclusions must remain visible. An unsupported operating system must not be presented as tested support.

## Reporting a problem

Use GitHub private vulnerability reporting if it is enabled for this repository. Otherwise open a minimal issue requesting a private contact route, without secrets, private payloads or a destructive reproduction. A normal bug report can include a small original synthetic fixture and the relevant JSON outcome.

Do not run a destructive proof of concept on a real working tree or somebody else's data.
