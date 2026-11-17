# Contributing

Keep the tool small: observable filesystem convergence, explicit trust boundaries and truthful incomplete/error states. A plugin framework, hosted agent, implicit command discovery or universal correctness claim is outside the v0.1 scope.

## Setup

Python 3.10+; Python 3.12 is a convenient local development target.

```sh
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check .
uv run --extra dev python -m build
```

Do not add runtime dependencies for formatting or argument parsing that the standard library already supports. New optional capabilities need a concrete user job and a discussion of their comparison/trust boundary.

## Changes

1. Write one failing behavioral test. Run it and check that the failure demonstrates the missing behavior.
2. Make the smallest working change and exercise the real CLI path.
3. Run the complete suite and Ruff; build/install the wheel if packaging or resources changed.
4. Update the specification and docs when the user contract changes. Never quietly weaken a comparison, ignore an error, skip a test or label unknown coverage clean.
5. Include the observed commands/results, remaining limitations and any compatibility impact in your pull request.

Use disposable, original synthetic fixtures. No customer data, production credentials, live services or destructive host tests. Tests of execution must terminate and reap their ordinary children and clean owned temporary resources. Run untrusted code only in an independently configured confinement environment, not through this tool as if it provided one.

## Reproductions

The best issue contains a small fixture, explicit command argv, expected first result, observed second-run difference, OS/Python version and a redacted JSON receipt. A screenshot of a green exit code is not enough. Do not require a model subscription or paid service to reproduce a package bug.

## License

Contributions are under Apache-2.0. Identify the source and license of any reused material; do not copy code or fixtures from incompatible-licensed projects. Research citations do not transfer implementation rights.
