"""
Packs — swappable domain blocks on top of base Saturn.

A pack is a folder here (`packs/<name>/`) that tailors the same base agent to one kind of
user — a bio or chem lab, say — without touching the engine. Its `__init__.py` declares:

  TOOLKITS  {key: toolspec.Toolkit(..., pack=<name>, prompt=<one prompt line>)}
  MODULES   the tool modules to import, in order — a module's tools register under the
            toolkit of its own name (packs/biochem/labmath.py -> "labmath"), as in tools/

and optionally a `bench` module with `tasks()`: the pack's loop-benchmark tasks
(bench/tasks.py appends them). Its third-party dependencies are the pack's extra in
pyproject.toml (`pip install 'saturn-agent[<name>]'`).

What a pack gets from base Saturn, unchanged: the gate (its tools declare a risk tier like any
tool), the trace, /tools (a pack toolkit is OFF until `/tools on <key>`, see
tools/registry.toolkit_on), and the system prompt (its `prompt` line joins it only while the
toolkit is on — core/messages.agent_sys_text). A pack whose dependencies are not installed
does not load and says so in the startup report (problems()); base Saturn runs as before.
"""

from __future__ import annotations

import importlib

# The packs this build ships, in the order /tools lists their toolkits.
PACKS = ("biochem",)

_loaded: list[str] = []
_problems: list[str] = []


def load() -> None:
    """Add every pack's toolkits and import its tool modules (tools/registry calls this once,
    after the base tools). A pack missing a dependency is taken back out whole — no toolkit
    left behind without its tools — and reported."""
    from tools.toolspec import TOOLKITS, add_toolkit

    for name in PACKS:
        if name in _loaded:
            continue
        pack = importlib.import_module(f"{__name__}.{name}")
        for key, kit in pack.TOOLKITS.items():
            if key in TOOLKITS:
                raise ValueError(f"pack {name}: toolkit {key!r} already exists")
            add_toolkit(key, kit)
        try:
            for module in pack.MODULES:
                importlib.import_module(f"{__name__}.{name}.{module}")
        except ImportError as exc:
            for key in pack.TOOLKITS:
                TOOLKITS.pop(key, None)
            _problems.append(f"the {name} pack did not load ({exc.name or exc} is not "
                             f"installed): pip install 'saturn-agent[{name}]'")
            continue
        _loaded.append(name)


def loaded() -> list[str]:
    return list(_loaded)


def problems() -> list[str]:
    return list(_problems)


def bench_tasks() -> list:
    """Every loaded pack's loop-benchmark tasks (its `bench.tasks()`), in pack order."""
    tasks = []
    for name in _loaded:
        try:
            bench = importlib.import_module(f"{__name__}.{name}.bench")
        except ModuleNotFoundError:
            continue
        tasks += bench.tasks()
    return tasks
