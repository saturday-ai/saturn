"""Running the loop benchmark: pick the tasks (all, or some toolkits), force each task's setup
and undo it, grade every turn (bench/expect.grade), summarise by shape and by toolkit with
coverage, and compare two reports. The model is reached only through the `query` function the
caller passes (benchmark.run_query) — everything here runs offline in tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bench.expect import Fact, Gate, grade
from bench.tasks import HARNESS, TASKS
from bench.worlds import apps_world, fixtures, messaging_world

VERSION = 2


def select(tasks: list, spec: "str | None") -> list:
    """`--toolkit files,messages`: the tasks of those toolkits (`harness`: the guard tasks).
    None or empty: every task."""
    from tools.toolspec import TOOLKITS

    keys = [k.strip().lower() for k in str(spec or "").split(",") if k.strip()]
    if not keys:
        return tasks
    for key in keys:
        if key not in TOOLKITS and key != HARNESS:
            raise SystemExit(f"--toolkit: no toolkit named {key!r} (have: "
                             f"{', '.join(list(TOOLKITS) + [HARNESS])})")
    chosen = [t for t in tasks if t.toolkit in keys]
    if not chosen:
        raise SystemExit(f"--toolkit: no tasks for {', '.join(keys)} yet — the report's "
                         "coverage table lists the toolkits without any")
    return chosen


def skipped_for(task) -> "str | None":
    """The toolkit, turned off by the user (or --off), that this task cannot run without:
    its own, the one its Gate call is in, or the one every tool its Fact needs is in. A
    task's OWN forced setup is not the user's choice and never skips it."""
    from tools import registry
    from tools.toolspec import toolkit_of

    if task.toolkit != HARNESS and not registry.toolkit_on(task.toolkit):
        return task.toolkit
    expect = task.expect
    if isinstance(expect, Gate) and registry.is_off(expect.tool):
        return toolkit_of(expect.tool)
    if isinstance(expect, Fact) and expect.via and all(registry.is_off(n) for n in expect.via):
        return toolkit_of(expect.via[0])
    return None


class _forced:
    """Apply a task's budget and toolkits-off for its turn; undo both after."""

    def __init__(self, setup):
        self.setup = setup

    def __enter__(self):
        from config import get_config
        from tools import registry

        runtime = get_config()._data.setdefault("runtime", {})
        self._had_budget = "max_iterations" in runtime
        self._budget = runtime.get("max_iterations")
        if self.setup.budget is not None:
            runtime["max_iterations"] = self.setup.budget
        self._turned_off = registry.set_toolkits(list(self.setup.off), False) if self.setup.off else []
        return self

    def __exit__(self, *exc):
        from config import get_config
        from tools import registry

        runtime = get_config()._data.setdefault("runtime", {})
        if self._had_budget:
            runtime["max_iterations"] = self._budget
        else:
            runtime.pop("max_iterations", None)
        if self._turned_off:
            registry.set_toolkits(self._turned_off, True)
        return False


def run(graph, tasks: list, query) -> dict:
    """Run and grade `tasks`, each from freshly planted files, inside the planted messaging
    world and apps (nothing reaches the user's apps or the network). `query(graph, text, decline=, steer=)` is run_query. Returns {results, summary}."""
    results = []
    with fixtures() as planted, messaging_world(), apps_world():
        for i, task in enumerate(tasks, 1):
            off = skipped_for(task)
            if off:
                results.append({"id": task.id, "shape": task.shape, "toolkit": task.toolkit,
                                "skipped": off})
                print(f"  [{i:2d}/{len(tasks)}] {task.id:<24} SKIP  ({off} is off)")
                continue
            planted.reset()
            with _forced(task.setup):
                entry = query(graph, task.query, decline=task.setup.decline, steer=task.setup.steer)
            g = grade(task, entry, planted.root)
            result = {"id": task.id, "shape": task.shape, "toolkit": task.toolkit,
                      "query": task.query, **g,
                      "tools_called": entry.get("tools_called", []),
                      "capped": entry.get("capped", False),
                      "context_tokens": entry.get("context_tokens"),
                      "think": entry.get("think", []),
                      "response": str(entry.get("response") or entry.get("error") or "")[:400]}
            results.append(result)
            print(f"  [{i:2d}/{len(tasks)}] {task.id:<24} {_verdict(result)}  "
                  f"({g['efficiency'].get('passes')} passes, {g['efficiency'].get('latency_s')}s, "
                  f"tools={','.join(result['tools_called']) or '-'})")
    return {"results": results, "summary": summarize(results, TASKS)}


def _verdict(r: dict) -> str:
    if r["passed"]:
        return "PASS"
    if r["safety"]:
        return "UNSAFE " + ", ".join(r["safety"])
    return "WRONG  " + str(r["why"])


def _group(rows: list) -> dict:
    n = len(rows)
    return {"n": n,
            "passed": sum(1 for r in rows if r["passed"]),
            "correct": sum(1 for r in rows if r["correct"]),
            "unsafe": sum(1 for r in rows if r["safety"]),
            "mean_passes": round(sum(r["efficiency"]["passes"] for r in rows) / n, 2),
            "mean_latency_s": round(sum(float(r["efficiency"]["latency_s"] or 0) for r in rows) / n, 2)}


def summarize(results: list, suite: list) -> dict:
    """The three grades overall, by shape and by toolkit; efficiency totals; and coverage —
    tasks per toolkit in the whole SUITE, with the toolkits that have none listed."""
    from tools.toolspec import TOOLKITS

    skipped = [r["id"] for r in results if r.get("skipped")]
    ran = [r for r in results if not r.get("skipped")]
    by_shape: dict = {}
    by_toolkit: dict = {}
    for r in ran:
        by_shape.setdefault(r["shape"], []).append(r)
        by_toolkit.setdefault(r["toolkit"], []).append(r)
    # An MCP server's toolkit is the user's configuration, not something the suite can plant.
    keys = [k for k, kit in TOOLKITS.items() if not kit.managed_by] + [HARNESS]
    coverage = {k: sum(1 for t in suite if t.toolkit == k) for k in keys}
    eff = [r["efficiency"] for r in ran]
    return {
        "total": len(ran),
        "passed": sum(1 for r in ran if r["passed"]),
        "correct": sum(1 for r in ran if r["correct"]),
        "safety": {r["id"]: r["safety"] for r in ran if r["safety"]},
        "failed": {r["id"]: (", ".join(r["safety"]) if r["safety"] else r["why"])
                   for r in ran if not r["passed"]},
        "skipped": skipped,
        "skipped_toolkits": sorted({r["skipped"] for r in results if r.get("skipped")}),
        "by_shape": {k: _group(v) for k, v in by_shape.items()},
        "by_toolkit": {k: _group(v) for k, v in by_toolkit.items()},
        "efficiency": {
            "over_par": sum(e["over_par"] for e in eff),
            "hygiene": sum(e["hygiene"] for e in eff),
            "wasted": sum(len(e["wasted"]) for e in eff),
            "mean_latency_s": round(sum(float(e["latency_s"] or 0) for e in eff) / len(eff), 2) if eff else 0.0,
        },
        "coverage": coverage,
        "uncovered": [k for k in keys if k != HARNESS and not coverage[k]],
        "thinking": summarize_thinking(ran),
    }


def summarize_thinking(results: list) -> dict:
    """What thinking cost and what came of it across the run, off each task's per-pass think
    records (core/think.entry): passes in all, passes that thought, drafts discarded for a
    thought, thoughts that came back empty or were cut, the seconds spent thinking, and the
    prompt-eval seconds of the passes."""
    entries = [e for r in results for e in (r.get("think") or []) if isinstance(e, dict)]
    asked = [e for e in entries if e.get("asked")]
    return {
        "passes": len(entries),
        "thought": len(asked),
        "drafts": sum(1 for e in entries if e.get("draft")),
        "empty": sum(1 for e in asked if e.get("outcome") == "empty"),
        "cut": sum(1 for e in asked if str(e.get("outcome") or "").startswith("cut-")),
        "seconds": round(sum(float(e.get("seconds") or 0.0) for e in asked), 2),
        "prompt_seconds": round(sum(float(e.get("prompt_s") or 0.0) for e in entries), 2),
    }


def print_summary(s: dict) -> None:
    eff, th = s["efficiency"], s["thinking"]
    print(f"\n{s['passed']}/{s['total']} passed · safety: {len(s['safety'])} unsafe · "
          f"correct {s['correct']}/{s['total']}"
          + (f" · {len(s['skipped'])} skipped ({', '.join(s.get('skipped_toolkits') or [])} off)"
             if s["skipped"] else ""))
    print(f"efficiency: {eff['over_par']} passes over par · {eff['hygiene']} hygiene bounces · "
          f"{eff['wasted']} wasted calls · mean {eff['mean_latency_s']}s")
    print(f"thinking: {th['thought']} of {th['passes']} passes thought ({th['seconds']}s) · "
          f"{th['drafts']} drafts rethought · {th['empty']} empty · {th['cut']} cut")
    for label, groups in (("toolkit", s["by_toolkit"]), ("shape", s["by_shape"])):
        for key, v in groups.items():
            print(f"  {label} {key:<10} {v['passed']}/{v['n']} passed · {v['unsafe']} unsafe · "
                  f"mean passes {v['mean_passes']} · mean {v['mean_latency_s']}s")
    if s["uncovered"]:
        print(f"uncovered toolkits (no tasks yet): {', '.join(s['uncovered'])}")


def report_path(log_dir: Path, tier: str, label: str, run: int = 0, runs: int = 1) -> Path:
    """loop_<tier>_<think>_<timestamp>[_<n>].json — the tier and the think mode are in the
    name, so a comparison across modes is a directory listing."""
    suffix = f"_{run}" if runs > 1 else ""
    return log_dir / f"loop_{tier}_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}.json"


def _status(r: dict) -> str:
    if r.get("passed"):
        return "pass"
    return ("unsafe: " + ", ".join(r["safety"])) if r.get("safety") else str(r.get("why"))


def compare(a: dict, b: dict) -> list:
    """`--compare A B`: the tasks whose grade changed from report A to report B, then the
    summary's moves. Version 2 reports only — v1 graded differently."""
    for rep in (a, b):
        if rep.get("version") != VERSION:
            raise SystemExit("--compare reads version 2 loop reports (2026-10-07 on); "
                             "an older report graded differently")
    old = {r["id"]: r for r in a.get("loop", []) if not r.get("skipped")}
    new = {r["id"]: r for r in b.get("loop", []) if not r.get("skipped")}
    lines = []
    for tid in list(old) + [t for t in new if t not in old]:
        if tid not in new:
            lines.append(f"{tid}: only in A")
            continue
        if tid not in old:
            lines.append(f"{tid}: only in B ({_status(new[tid])})")
            continue
        before, after = _status(old[tid]), _status(new[tid])
        if before == after:
            continue
        if after == "pass":
            lines.append(f"{tid}: fixed ({before} → pass)")
        elif before == "pass":
            lines.append(f"{tid}: broke (→ {after})")
        else:
            lines.append(f"{tid}: changed ({before} → {after})")
    sa, sb = a.get("loop_summary", {}), b.get("loop_summary", {})
    lines.append(f"passed {sa.get('passed')}/{sa.get('total')} → {sb.get('passed')}/{sb.get('total')} · "
                 f"unsafe {len(sa.get('safety') or {})} → {len(sb.get('safety') or {})} · "
                 f"over par {sa.get('efficiency', {}).get('over_par')} → {sb.get('efficiency', {}).get('over_par')} · "
                 f"mean {sa.get('efficiency', {}).get('mean_latency_s')}s → {sb.get('efficiency', {}).get('mean_latency_s')}s")
    return lines
