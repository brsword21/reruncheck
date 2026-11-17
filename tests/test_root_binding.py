import sys
from pathlib import Path

from reruncheck.runner import check


def test_fixture_root_swapped_to_symlink_before_resolution_is_rejected(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    outside = tmp_path / "outside"
    fixture.mkdir()
    outside.mkdir()
    (fixture / "expected.txt").write_text("original synthetic fixture")
    (outside / "outside.txt").write_text("synthetic data outside the selected fixture")
    real_resolve = Path.resolve
    swapped = False

    def swap_before_resolve(self, *args, **kwargs):
        nonlocal swapped
        if self == fixture and not swapped:
            swapped = True
            fixture.rename(tmp_path / "held")
            fixture.symlink_to(outside, target_is_directory=True)
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", swap_before_resolve)
    result = check(fixture, [sys.executable, "-c", "pass"], trust_command=True)
    assert swapped
    assert result.exit_code == 2
    assert result.outcome.value == "error"
    assert result.commands == []
    assert "original" not in result.observations
    assert (outside / "outside.txt").read_text() == "synthetic data outside the selected fixture"
