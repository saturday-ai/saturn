"""
Packs (packs/) — the swappable domain blocks on top of base Saturn — and the first one's
toolkit, the biochem pack's lab math (packs/biochem/labmath.py).
"""

import pytest

LABMATH = ["dilution", "molar_solution", "serial_dilution", "buffer_recipe", "molecular_weight"]


@pytest.fixture
def rebinds(monkeypatch):
    from core import llms

    calls: list = []
    monkeypatch.setattr(llms, "reset_models", lambda: calls.append(1))
    return calls


def _call(name, **args):
    from tools.registry import all_by_name

    return all_by_name[name].invoke(args)


def _refused(name, **args) -> str:
    from tools.toolspec import ToolError

    with pytest.raises(ToolError) as exc:
        _call(name, **args)
    return str(exc.value)


# ── the pack seam (packs/__init__.py, tools/registry, core/messages) ────────────────────────


def test_the_biochem_pack_loads_its_toolkit_and_tools():
    import packs
    from tools import registry, toolspec

    assert packs.loaded() == ["biochem"] and packs.problems() == []
    assert toolspec.TOOLKITS["labmath"].pack == "biochem"
    assert [t.name for t in registry.toolkit_tools("labmath")] == LABMATH
    assert all(registry.DECLARED_RISK[n] == "read_only" for n in LABMATH)


def test_a_pack_toolkit_is_off_until_turned_on(rebinds):
    from tools import registry

    assert not registry.toolkit_on("labmath")
    assert not set(LABMATH) & set(registry.tools_by_name)
    assert all(registry.is_off(n) for n in LABMATH)

    assert registry.set_toolkits(["labmath"], True) == ["labmath"]
    assert set(LABMATH) <= set(registry.tools_by_name) and registry.packs_on() == ["labmath"]
    assert rebinds == [1]

    registry.set_toolkits(["labmath"], False)
    assert not set(LABMATH) & set(registry.tools_by_name)


def test_only_an_explicit_true_turns_a_pack_on(monkeypatch):
    from config import get_config
    from tools import registry

    for value, on in ((True, True), (False, False), ("yes", False), (1, False), (None, False)):
        monkeypatch.setitem(get_config()._data, "toolkits", {"labmath": value})
        assert registry.toolkit_on("labmath") is on, value
    monkeypatch.setitem(get_config()._data, "toolkits", {"labmath": "yes"})
    assert any("labmath is off" in p for p in registry.toolkit_problems())


def test_the_base_prompt_does_not_move_while_the_pack_is_off():
    from core import messages

    assert messages.agent_sys_msg().content == messages._AGENT_SYS
    assert "dilution" not in messages._AGENT_SYS


def test_the_pack_line_joins_the_prompt_while_on_and_is_never_called_off(rebinds):
    from core import messages
    from tools import registry, toolspec

    registry.set_toolkits(["labmath"], True)
    text = messages.agent_sys_msg().content
    line = toolspec.TOOLKITS["labmath"].prompt
    assert text.count(line) == 1 and text.index(line) < text.index("\n\nRules:")
    for name in LABMATH:
        assert name in line
    assert "turned off" not in text

    registry.set_toolkits(["labmath"], False)
    registry.set_toolkits(["web"], False)
    off = messages.agent_sys_msg().content
    assert line not in off
    assert [ln for ln in off.splitlines() if "turned off" in ln][0].endswith(
        "`/tools on <name>` turns it on.") and "labmath" not in off


def test_with_the_pack_on_and_a_base_toolkit_off_both_lines_land_before_the_rules():
    from core import messages
    from tools import toolspec

    text = messages.agent_sys_text(frozenset({"web", "labmath"}), frozenset({"labmath"}))
    head = text.split("\n\nRules:")[0]
    assert toolspec.TOOLKITS["labmath"].prompt in head and "turned off by the user: web." in head
    for line in text.splitlines():
        assert line == line.rstrip() and line.strip() != "-"


def test_a_pack_missing_a_dependency_is_reported_and_leaves_nothing_behind(monkeypatch):
    import importlib
    import sys
    import types

    import packs
    from tools import toolspec

    fake = types.ModuleType("packs.fakepack")
    fake.TOOLKITS = {"fakekit": toolspec.Toolkit("Fake", "nothing", pack="fakepack")}
    fake.MODULES = ("tools_needing_x",)
    monkeypatch.setitem(sys.modules, "packs.fakepack", fake)
    real = importlib.import_module

    def import_module(name, *a):
        if name == "packs.fakepack.tools_needing_x":
            raise ModuleNotFoundError("No module named 'xlib'", name="xlib")
        return real(name, *a)

    monkeypatch.setattr(packs.importlib, "import_module", import_module)
    monkeypatch.setattr(packs, "PACKS", ("fakepack",))
    monkeypatch.setattr(packs, "_problems", [])
    packs.load()

    assert "fakekit" not in toolspec.TOOLKITS and "fakepack" not in packs.loaded()
    assert packs.problems() == ["the fakepack pack did not load (xlib is not installed): "
                                "pip install 'saturn-agent[fakepack]'"]


def test_the_startup_report_names_a_pack_that_did_not_load(monkeypatch):
    import packs
    from app import startup

    monkeypatch.setattr(packs, "_problems", ["the x pack did not load"])
    assert "the x pack did not load" in startup.problems()


# ── the benchmark: a pack task runs either way ───────────────────────────────────────────────


def test_a_pack_task_runs_with_its_toolkit_off_as_the_baseline(rebinds):
    from bench.loop import skipped_for
    from bench.tasks import task
    from tools import registry

    t = task("lab_stock_volume")
    assert skipped_for(t) is None
    registry.set_toolkits(["labmath"], True)
    assert skipped_for(t) is None


def test_every_pack_fact_accepts_the_base_calculator():
    from bench.expect import Fact
    from bench.tasks import TASKS

    for t in [t for t in TASKS if t.toolkit == "labmath"]:
        if isinstance(t.expect, Fact) and t.expect.via:
            assert "calculate" in t.expect.via and "calculate" in t.tools, t.id


def test_bench_on_turns_a_pack_on_in_memory_only(rebinds):
    import benchmark
    from tools import registry

    assert benchmark.apply_on("labmath") == ["labmath"]
    assert registry.toolkit_on("labmath")
    with pytest.raises(SystemExit, match="no toolkit"):
        benchmark.apply_on("nosuch")


# ── the lab math (packs/biochem/labmath.py) ─────────────────────────────────────────────────


def test_dilution_solves_for_the_stock_volume_and_says_the_recipe():
    out = _call("dilution", c1="10 mM", c2="200 uM", v2="50 uL")

    assert out["v1"] == "1 µL"
    assert out["recipe"] == "1 µL of the 10 mM stock + 49 µL of diluent = 50 µL at 200 µM"
    assert out["work"].startswith("V1 = C2 × V2 ÷ C1")


@pytest.mark.parametrize("args, key, value", [
    (dict(c1="50X", c2="1X", v2="200 mL"), "v1", "4 mL"),
    (dict(c1="10 mM", v1="5 uL", c2="100 uM"), "v2", "500 µL"),
    (dict(v1="20 uL", c2="1 mg/mL", v2="1 mL"), "c1", "50 mg/mL"),
    (dict(c1="5 mg/mL", v1="20 µL", v2="1 mL"), "c2", "100 µg/mL"),
    (dict(c1="1 M", c2="150 mM", v2="1 L"), "v1", "150 mL"),
    (dict(c1="2.5 μM", c2="100 nM", v2="10 mL"), "v1", "400 µL"),   # Greek mu
])
def test_dilution_solves_each_of_the_four(args, key, value):
    assert _call("dilution", **args)[key] == value


def test_dilution_gives_the_diluent_for_a_fold_stock():
    assert "196 mL of diluent" in _call("dilution", c1="50X", c2="1X", v2="200 mL")["recipe"]


@pytest.mark.parametrize("args, said", [
    (dict(c1="1 mM", c2="5 mM", v2="1 mL"), "cannot concentrate"),
    (dict(c1="10 mM", v1="2 mL", v2="1 mL"), "cannot concentrate"),
    (dict(c1="10 mM", v2="1 mL"), "exactly three"),
    (dict(c1="10 mM", v1="1 uL", c2="1 mM", v2="10 uL"), "exactly three"),
    (dict(c1="10 mM", c2="5 mg/mL", v2="1 mL"), "different kinds"),
    (dict(c1="10 mm", c2="1 mM", v2="1 mL"), "not a molar concentration"),   # millimetres
    (dict(c1="10 mM", c2="1 mM", v2="1 g"), "not a volume"),
    (dict(c1="ten", c2="1 mM", v2="1 mL"), "cannot read"),
    (dict(c1="0 mM", c2="1 mM", v2="1 mL"), "more than zero"),
    (dict(c1="-1 mM", c2="1 mM", v2="1 mL"), "more than zero"),
])
def test_dilution_refuses_what_it_cannot_answer(args, said):
    assert said in _refused("dilution", **args)


def test_molar_solution_weighs_from_a_formula():
    out = _call("molar_solution", concentration="150 mM", volume="500 mL", formula="NaCl")

    assert out["mass"] == "4.383 g" and out["molecular_weight"] == "58.44 g/mol"
    assert "58.44 g/mol" in out["work"] and out["recipe"].startswith("weigh 4.383 g")


@pytest.mark.parametrize("args, key, value", [
    (dict(mass="4.383 g", volume="500 mL", formula="NaCl"), "concentration", "150 mM"),
    (dict(concentration="150 mM", mass="4.383 g", molecular_weight="58.44"), "volume", "500 mL"),
    (dict(concentration="1 M", volume="1 L", molecular_weight="58.44 g/mol"), "mass", "58.44 g"),
    (dict(concentration="2 mg/mL", volume="10 mL"), "mass", "20 mg"),
    (dict(mass="20 mg", volume="10 mL"), "concentration", "2 mg/mL"),
    (dict(concentration="10 mM", volume="100 mL", formula="CuSO4·5H2O"), "mass", "249.7 mg"),
])
def test_molar_solution_solves_each_of_the_three(args, key, value):
    assert _call("molar_solution", **args)[key] == value


@pytest.mark.parametrize("args, said", [
    (dict(concentration="150 mM", volume="500 mL"), "needs the compound"),
    (dict(concentration="150 mM", volume="500 mL", formula="Xq2"), "chemical formula"),
    (dict(concentration="150 mM", volume="500 mL", molecular_weight="heavy"), "g/mol"),
    (dict(concentration="150 mM", volume="500 mL", molecular_weight="-5"), "more than zero"),
    (dict(concentration="5X", volume="500 mL", formula="NaCl"), "not a molar"),
    (dict(volume="500 mL", formula="NaCl"), "exactly three"),
])
def test_molar_solution_refuses_what_it_cannot_answer(args, said):
    assert said in _refused("molar_solution", **args)


def test_serial_dilution_lists_every_tube_and_the_transfer():
    out = _call("serial_dilution", start="1 mM", factor="1:10", steps=5, tube_volume="1 mL")

    assert [t["concentration"] for t in out["tubes"]] == [
        "100 µM", "10 µM", "1 µM", "100 nM", "10 nM"]
    assert out["each_tube"].startswith("900 µL of diluent, then 100 µL from the tube before")
    assert "the last keeps 1 mL" in out["volumes"]


@pytest.mark.parametrize("factor", ["2", "1:2", "1/2", "2x", "2X"])
def test_serial_dilution_reads_a_factor_however_it_is_written(factor):
    out = _call("serial_dilution", start="8 uM", factor=factor, steps=3, tube_volume="200 uL")
    assert [t["concentration"] for t in out["tubes"]] == ["4 µM", "2 µM", "1 µM"]


@pytest.mark.parametrize("args, said", [
    (dict(start="1 mM", factor="1", steps=3, tube_volume="1 mL"), "above 1"),
    (dict(start="1 mM", factor="ten", steps=3, tube_volume="1 mL"), "above 1"),
    (dict(start="1 mM", factor="10", steps=0, tube_volume="1 mL"), "between 1 and 24"),
    (dict(start="1 mM", factor="10", steps=25, tube_volume="1 mL"), "between 1 and 24"),
    (dict(start="1 mM", factor="10", steps=3, tube_volume="1 mM"), "not a volume"),
])
def test_serial_dilution_refuses_what_it_cannot_answer(args, said):
    assert said in _refused("serial_dilution", **args)


def test_a_tris_buffer_weighs_tris_base_and_titrates_with_hcl():
    out = _call("buffer_recipe", buffer="Tris-HCl", ph=8.0, concentration="50 mM", volume="1 L")

    assert out["recipe"].startswith("dissolve 6.057 g Tris base")
    assert "with HCl (about 27.01 mmol" in out["recipe"]
    assert out["pka"] == "8.07 at 25 °C" and "pH meter" in out["note"]


def test_tris_shifts_with_temperature():
    cold = _call("buffer_recipe", buffer="tris", ph=8.0, concentration="50 mM", volume="1 L",
                 temperature=4)
    assert cold["pka"] == "8.66 at 4 °C"          # 8.07 − 0.028 × 21


def test_a_good_buffer_is_titrated_up_with_naoh():
    out = _call("buffer_recipe", buffer="HEPES", ph=7.48, concentration="20 mM", volume="500 mL")

    assert out["recipe"].startswith("dissolve 2.383 g HEPES (free acid)")
    assert "NaOH (about 5 mmol" in out["recipe"]                    # half, at the pKa


def test_a_phosphate_buffer_mixes_both_salts():
    out = _call("buffer_recipe", buffer="sodium phosphate", ph=7.4, concentration="100 mM",
                volume="500 mL")

    assert "2.321 g NaH2PO4" in out["recipe"] and "4.352 g Na2HPO4" in out["recipe"]


def test_an_acetate_buffer_gives_the_acid_as_a_volume_too():
    out = _call("buffer_recipe", buffer="acetate", ph=4.76, concentration="100 mM", volume="1 L")

    assert "3.002 g acetic acid (2.862 mL glacial)" in out["recipe"]


@pytest.mark.parametrize("args, said", [
    (dict(buffer="tris", ph=5.0, concentration="50 mM", volume="1 L"), "cover it: acetate"),
    (dict(buffer="bicarbonate", ph=7.0, concentration="50 mM", volume="1 L"), "known buffers"),
    (dict(buffer="tris", ph=8.0, concentration="5 mg/mL", volume="1 L"), "not a molar"),
    (dict(buffer="tris", ph=8.0, concentration="50 mM", volume="1 kg"), "not a volume"),
])
def test_buffer_recipe_refuses_what_it_cannot_answer(args, said):
    assert said in _refused("buffer_recipe", **args)


def test_the_buffer_tables_masses_are_their_formulas():
    """A typo in the pKa table's masses would weigh every recipe wrong: each is checked
    against the formula's own mass."""
    from molmass import Formula

    from packs.biochem.labmath import _BUFFERS

    formulas = {"Tris base": "C4H11NO3", "HEPES (free acid)": "C8H18N2O4S",
                "MOPS (free acid)": "C7H15NO4S", "PIPES (free acid)": "C8H18N2O6S2",
                "MES (free acid)": "C6H13NO4S", "NaH2PO4 (monobasic, anhydrous)": "NaH2PO4",
                "Na2HPO4 (dibasic, anhydrous)": "Na2HPO4", "acetic acid": "C2H4O2",
                "sodium acetate (anhydrous)": "C2H3NaO2"}
    for b in _BUFFERS.values():
        for what, mw in [b[k] for k in ("weigh", "acid", "base") if k in b]:
            assert abs(Formula(formulas[what]).mass - mw) < 0.02, what


@pytest.mark.parametrize("formula, mw", [
    ("NaCl", "58.44 g/mol"), ("C4H11NO3", "121.14 g/mol"), ("CuSO4·5H2O", "249.68 g/mol"),
    ("CuSO4.5H2O", "249.68 g/mol"), ("Na2HPO4*7H2O", "268.07 g/mol"),
])
def test_molecular_weight_reads_hydrates_however_the_dot_is_written(formula, mw):
    assert _call("molecular_weight", formula=formula)["molecular_weight"] == mw


def test_molecular_weight_refuses_a_non_formula():
    assert "chemical formula" in _refused("molecular_weight", formula="table salt")
