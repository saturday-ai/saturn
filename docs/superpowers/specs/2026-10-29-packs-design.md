# Packs — swappable domain blocks on top of base Saturn (2026-10-29)

## Why

Saturn is pitched two ways: to consumers (privacy, no cloud database) and to organisations.
For the second, the near-term target is University of Michigan labs and clubs: the same
offline agent, tailored to one lab's research. The tailoring has to be a *block* — swapped
per lab or company, without forking the engine — so it is a pack.

## What a pack is

A folder `packs/<name>/` with:

| Piece | What | Where it plugs in |
|---|---|---|
| `TOOLKITS` | `{key: Toolkit(..., pack=<name>, prompt=<one line>)}` | `toolspec.TOOLKITS`, /tools |
| `MODULES` | tool modules, `@register_tool` as in `tools/` | the registry, the gate, the trace |
| `bench.py` (optional) | `tasks()` → loop-benchmark tasks | `bench/tasks.TASKS` |
| extra in `pyproject.toml` | its third-party imports | `pip install 'saturn-agent[<name>]'` |

Later layers (not built): a pack's instructions and skills, a seeded knowledge base, a
glossary for the `entities` memory layer, and a model adapter (`tiers.<t>.model`).

## Rules

1. **Off by default.** A pack toolkit is on only when `toolkits.<key>` is exactly `true`.
   With every pack off, the bound tools and the system prompt are base Saturn's, byte for byte.
2. **One line in the prompt.** An on pack toolkit adds its `prompt` line before `Rules:`;
   an off one is not named anywhere (it is not a choice the user made).
3. **Same trust.** Pack tools declare a risk tier like any tool; unknown fails closed.
4. **Fails soft.** A pack whose dependencies are missing does not load — none of its
   toolkits stay behind — and the startup report says how to install it.
5. **Measured.** A pack's benchmark tasks run with the pack off too: off is the baseline,
   `--on <key>` the pack, `--compare` the gain. Its Facts accept `calculate`, so the baseline
   is graded on its answer. The base suite's 60-task cap does not count pack tasks.

## The first pack: biochem → `labmath`

Small local models get bench arithmetic and unit prefixes wrong; a wrong reagent amount
costs an experiment. Five read_only tools, units by pint, formula masses by molmass:

- `dilution(c1, v1, c2, v2)` — C1V1 = C2V2 for the one left empty; molar, mass/volume or
  fold ("10X"); refuses a "dilution" that concentrates and mixed kinds of concentration.
- `molar_solution(concentration, volume, mass, formula | molecular_weight)` — the one empty.
- `serial_dilution(start, factor, steps, tube_volume)` — the tube table and the transfer.
- `buffer_recipe(buffer, ph, concentration, volume, temperature)` — Henderson–Hasselbalch
  over a pKa table (Tris, HEPES, MOPS, PIPES, MES, phosphate, acetate) with dpKa/dT; a
  titrated buffer gets the mass and the titrant, a two-salt buffer both masses; refuses a pH
  outside pKa ± 1 and names the buffers that cover it.
- `molecular_weight(formula)` — hydrates with `.`, `·` or `*`.

Every result carries its formula and numbers (`work`) so the user can check it.

## Next

- Run `benchmark.py --loop --toolkit labmath` with and without `--on labmath` on the 4b and
  9b models; the difference is the demo number.
- A sample of a target lab's instrument export (plate reader, qPCR) → the next pack tool.
- `/pack use <name>` once there is more than one pack: turn its toolkits on as a set.
