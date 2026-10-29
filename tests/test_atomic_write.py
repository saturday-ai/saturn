"""diag.atomic_write_text — the one crash-safe write behind memory.md, permissions.json, the
pending-review queue, a saved skill and the session autosave."""

import os
from pathlib import Path

import pytest


def test_a_write_lands_whole_and_leaves_no_temp_file(tmp_path):
    import diag

    target = tmp_path / "memory" / "memory.md"
    diag.atomic_write_text(target, "## user\n- a fact\n")
    assert target.read_text(encoding="utf-8") == "## user\n- a fact\n"
    assert [p.name for p in target.parent.iterdir()] == ["memory.md"]


def test_two_writers_never_share_a_temp_file(tmp_path, monkeypatch):
    """Two Saturn processes (a REPL's `/memory review` and a headless turn's `remember`)
    writing memory.md at once each get their own temp file: one fixed `<name>.tmp` let one
    install the other's half-written text, or unlink the temp the other was about to rename."""
    import diag

    target = tmp_path / "memory.md"
    temps = []

    def replace(src, dst):
        temps.append(Path(src))
        raise OSError("simulated")

    monkeypatch.setattr(os, "replace", replace)
    for _ in range(2):
        with pytest.raises(OSError, match="simulated"):
            diag.atomic_write_text(target, "x")
    assert len(temps) == 2 and temps[0] != temps[1]
    assert list(tmp_path.iterdir()) == []       # a failed write takes its temp file with it
