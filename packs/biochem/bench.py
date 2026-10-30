"""The biochem pack's loop-benchmark tasks (packs.bench_tasks; bench/tasks.py appends them).

Each task is a bench calculation a lab asks every day. A pack task runs whether its toolkit is
on or not (bench/loop.skipped_for): off is base Saturn with only `calculate` — the baseline —
so `python benchmark.py --loop --toolkit labmath` and the same with `--on labmath`, then
`--compare`, is the pack's measured gain. Every Fact accepts `calculate` as well as the lab
tool, so the baseline is graded on its numbers, not on a tool it does not have."""

from __future__ import annotations


def tasks() -> list:
    from bench.expect import Fact
    from bench.tasks import _t

    def via(*names):
        return tuple(names) + ("calculate",)

    def allowed(*names):
        return frozenset(names) | {"calculate", "plan"}

    return [
        _t("lab_stock_volume", "lookup", "labmath",
           "How much of my 10 mM ATP stock do I need to make 50 µL at 200 µM?",
           Fact(["1 µl", "1 μl", "1 ul", "1 microliter", "1.0 µl"], via=via("dilution")),
           "a stock volume worked out in the head, off by a unit prefix",
           tools=allowed("dilution"), par=2,
           ideal=[("dilution", {"c1": "10 mM", "c2": "200 uM", "v2": "50 uL"})]),
        _t("lab_fold_dilution", "lookup", "labmath",
           "I need 200 mL of 1X TAE from my 50X stock. How much water do I add?",
           Fact(["196 ml", "196ml", "196 milliliters"], via=via("dilution")),
           "the stock volume given as the answer instead of the diluent",
           tools=allowed("dilution"), par=2,
           ideal=[("dilution", {"c1": "50X", "c2": "1X", "v2": "200 mL"})]),
        _t("lab_molar_mass", "lookup", "labmath",
           "How many grams of NaCl do I weigh out for 500 mL of 150 mM?",
           Fact(["4.38"], via=via("molar_solution", "molecular_weight")),
           "a molecular weight recalled wrong, or mL taken as L",
           tools=allowed("molar_solution", "molecular_weight"), par=2,
           ideal=[("molar_solution", {"concentration": "150 mM", "volume": "500 mL",
                                      "formula": "NaCl"})]),
        _t("lab_hydrate_mw", "lookup", "labmath",
           "What's the molecular weight of copper(II) sulfate pentahydrate, CuSO4·5H2O?",
           Fact(["249.68", "249.69", "249.7"], via=via("molecular_weight")),
           "the anhydrous mass given for a hydrate",
           tools=allowed("molecular_weight"), par=2,
           ideal=[("molecular_weight", {"formula": "CuSO4·5H2O"})]),
        _t("lab_tris_buffer", "lookup", "labmath",
           "How much Tris base do I weigh for 1 L of 50 mM Tris-HCl, pH 8.0?",
           Fact(["6.06", "6.057"], via=via("buffer_recipe", "molar_solution")),
           "Tris-HCl's molecular weight used for Tris base",
           tools=allowed("buffer_recipe", "molar_solution", "molecular_weight"), par=2,
           ideal=[("buffer_recipe", {"buffer": "tris", "ph": 8.0, "concentration": "50 mM",
                                     "volume": "1 L"})]),
        _t("lab_serial_last", "lookup", "labmath",
           "I'm doing a 1:10 serial dilution of a 1 mM stock across 5 tubes, 1 mL each. "
           "What's the concentration in the last tube, and how much do I transfer each time?",
           Fact(["10 nm", "0.01 µm", "0.01 μm", "0.01 um", "10 nanomolar"],
                via=via("serial_dilution", "dilution")),
           "one ten-fold step too many or too few",
           tools=allowed("serial_dilution", "dilution"), par=2,
           ideal=[("serial_dilution", {"start": "1 mM", "factor": "10", "steps": 5,
                                       "tube_volume": "1 mL"})]),
        _t("lab_hydrate_mass", "lookup", "labmath",
           "How many grams of MgCl2·6H2O do I need for 250 mL of 1 M MgCl2?",
           Fact(["50.83", "50.8 g"], via=via("molar_solution", "molecular_weight")),
           "the anhydrous molecular weight used to weigh a hydrate",
           tools=allowed("molar_solution", "molecular_weight"), par=2,
           ideal=[("molar_solution", {"concentration": "1 M", "volume": "250 mL",
                                      "formula": "MgCl2·6H2O"})]),
        _t("lab_prefix_chain", "lookup", "labmath",
           "I want 2 mL of a 5 µM working solution from my 2.5 mM stock. How much stock?",
           Fact(["4 µl", "4 ul", "4.0 µl", "4 microliter"], via=via("dilution")),
           "a factor of a thousand lost between mM and µM",
           tools=allowed("dilution"), par=2,
           ideal=[("dilution", {"c1": "2.5 mM", "c2": "5 uM", "v2": "2 mL"})]),
        _t("lab_mass_dilution", "lookup", "labmath",
           "My antibody stock is 20 mg/mL. How much do I add to make 10 mL at 50 µg/mL?",
           Fact(["25 µl", "25 ul", "25.0 µl", "25 microliter", "0.025 ml"],
                via=via("dilution")),
           "mg and µg mixed up in a mass-per-volume dilution",
           tools=allowed("dilution"), par=2,
           ideal=[("dilution", {"c1": "20 mg/mL", "c2": "50 ug/mL", "v2": "10 mL"})]),
        _t("lab_phosphate_pair", "lookup", "labmath",
           "Recipe for 1 L of 100 mM sodium phosphate buffer, pH 7.4, from anhydrous monobasic "
           "and dibasic salts: how many grams of the dibasic?",
           Fact(["8.70", "8.7 g"], via=via("buffer_recipe")),
           "the acid and base fractions swapped, or one salt's mass for both",
           tools=allowed("buffer_recipe", "molar_solution", "molecular_weight"), par=2,
           ideal=[("buffer_recipe", {"buffer": "phosphate", "ph": 7.4,
                                     "concentration": "100 mM", "volume": "1 L"})]),
        _t("lab_cold_tris", "lookup", "labmath",
           "I'm making 500 mL of 20 mM Tris pH 8.0 for the cold room, so the pH has to be right "
           "at 4 °C. About how much 1 M HCl will it take?",
           Fact(["8.2 ml", "8.20 ml", "8.198"], via=via("buffer_recipe")),
           "Tris's pKa taken at 25 °C for a buffer used at 4 °C",
           tools=allowed("buffer_recipe", "molar_solution", "molecular_weight"), par=2,
           ideal=[("buffer_recipe", {"buffer": "tris", "ph": 8.0, "concentration": "20 mM",
                                     "volume": "500 mL", "temperature": 4})]),
        _t("lab_cannot_concentrate", "robust", "labmath",
           "Using my 1 mM stock, make 1 mL at 5 mM. How much stock do I use?",
           Fact(["cannot", "can't", "not possible", "impossible", "higher than", "more "
                 "concentrated", "isn't possible", "is not possible", "won't work"]),
           "a volume made up for a dilution that would have to concentrate",
           tools=allowed("dilution"), par=2,
           ideal=[("dilution", {"c1": "1 mM", "c2": "5 mM", "v2": "1 mL"})]),
    ]
