"""One typed report drives both human and JSON results."""

from dataclasses import asdict, dataclass, field
from enum import Enum


class Outcome(str, Enum):
    CONVERGED = "converged"
    NONCONVERGENT = "nonconvergent"
    FIRST_RUN_MISMATCH = "first_run_mismatch"
    ERROR = "error"


@dataclass(frozen=True)
class Error:
    phase: str
    code: str
    message: str


@dataclass
class CheckReport:
    outcome: Outcome = Outcome.ERROR
    first_run_asserted: bool = False
    first_run_matches: bool | None = None
    converged: bool | None = None
    coverage: dict = field(default_factory=dict)
    commands: list = field(default_factory=list)
    changes: list = field(default_factory=list)
    expected_changes: list = field(default_factory=list)
    errors: list[Error] = field(default_factory=list)
    observations: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    environment_forwarded: list[str] = field(default_factory=list)

    @property
    def exit_code(self):
        if self.outcome is Outcome.ERROR:
            return 2
        return 0 if self.outcome is Outcome.CONVERGED else 1

    def to_dict(self):
        return {
            "schema_version": 1,
            **asdict(self),
            "outcome": self.outcome.value,
            "correctness_scope": "Convergence under recorded filesystem coverage is not "
            "general correctness; expected state is asserted only "
            "when first_run_asserted is true.",
            "execution_boundary": "Trusted commands, not an OS sandbox.",
        }
