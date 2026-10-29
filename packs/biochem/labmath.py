"""
Lab math — the bench calculations a wet lab does every day, computed, never recalled.

  dilution          C1·V1 = C2·V2, solved for whichever of the four is left blank
  molar_solution    concentration × volume × molecular weight = mass, solved for the blank one
  serial_dilution   the tube-by-tube transfer, diluent and concentration of a dilution series
  buffer_recipe     Henderson–Hasselbalch: what to weigh (and titrate) for a buffer at a pH
  molecular_weight  a formula's average mass, hydrates included ("CuSO4·5H2O")

All read_only and local: the same idea as core's `calculate` — a small model reads the request
and picks the tool; the units (pint) and the masses (molmass) are never its job. Every result
carries the formula and the numbers that went into it, so the user can check the work. A
quantity that cannot be read, has the wrong kind of unit, or asks for the impossible (a
"dilution" that concentrates) raises ToolError — a wrong reagent amount is worse than none.
"""

from __future__ import annotations

import re

import pint
from molmass import Formula

from tools.toolspec import ToolError, register_tool

_U = pint.UnitRegistry()
_Q = _U.Quantity

# A fold concentration: "10X", "1 x", "2×" — a stock buffer's strength, dimensionless.
_FOLD = re.compile(r"\s*(\d+(?:\.\d+)?|\.\d+)\s*[xX×]\s*")
_MICRO = str.maketrans({"µ": "u", "μ": "u"})

_VOLUME = "[volume]"
_MOLAR = "[substance] / [volume]"
_MASS_CONC = "[mass] / [volume]"
_MASS = "[mass]"

# The units a result is shown in, largest first: the first that gives a magnitude of 1 or more.
_SCALES = {
    _VOLUME: ("L", "mL", "uL", "nL"),
    _MOLAR: ("M", "mM", "uM", "nM", "pM"),
    _MASS_CONC: ("g/mL", "mg/mL", "ug/mL", "ng/mL"),
    _MASS: ("kg", "g", "mg", "ug", "ng"),
}


def _num(x: float) -> str:
    """Four significant figures, never in exponent notation: 0.0001234, 1235, 4.383."""
    v = float(f"{x:.4g}")
    return f"{v:.10f}".rstrip("0").rstrip(".") if not v.is_integer() else str(int(v))


def _kind(q) -> "str | None":
    if q.dimensionless:
        return ""
    return next((k for k in _SCALES if q.check(k)), None)


def _show(q) -> str:
    """A quantity in the unit a person would write it in: 4.383 g, 111.1 µL, 200 µM, 10X."""
    kind = _kind(q)
    if kind == "":
        return f"{_num(q.to('').magnitude)}X"
    units = _SCALES.get(kind)
    if not units:
        return f"{_num(q.magnitude)} {q.units:~P}"
    unit = next((u for u in units if abs(q.to(u).magnitude) >= 1), units[-1])
    return f"{_num(q.to(unit).magnitude)} {unit.replace('u', 'µ')}"


def _read(text, what: str, kinds: tuple):
    """`text` as a quantity of one of `kinds`; ToolError when it is not one, or not above
    zero."""
    raw = str(text).strip()
    fold = _FOLD.fullmatch(raw)
    try:
        q = _Q(float(fold.group(1)), "") if fold else _Q(raw.translate(_MICRO))
    except Exception:
        raise ToolError(f"{what}: cannot read {raw!r} as a quantity — give a number and a "
                        "unit, like '10 mM', '50 uL' or '2 mg/mL'") from None
    if not isinstance(q, _Q):
        q = _Q(q, "")
    kind = _kind(q)
    if kind not in kinds:
        wanted = " or ".join(_KIND_NAMES[k] for k in kinds)
        raise ToolError(f"{what}: {raw!r} is not a {wanted}")
    if q.magnitude <= 0:
        raise ToolError(f"{what} must be more than zero, not {raw!r}")
    return q


_KIND_NAMES = {
    _VOLUME: "volume (like '50 uL')",
    _MOLAR: "molar concentration (like '10 mM')",
    _MASS_CONC: "mass concentration (like '2 mg/mL')",
    _MASS: "mass (like '5 g')",
    "": "fold concentration (like '10X')",
}
_CONC = (_MOLAR, _MASS_CONC, "")


def _blank(**given) -> str:
    """The one argument left empty; ToolError unless exactly one is."""
    blank = [k for k, v in given.items() if v is None or not str(v).strip()]
    if len(blank) != 1:
        filled = ", ".join(given)
        raise ToolError(f"give exactly three of {filled} and leave the one to solve for empty "
                        f"(empty now: {', '.join(blank) or 'none'})")
    return blank[0]


@register_tool("read_only")
def dilution(c1: str = "", v1: str = "", c2: str = "", v2: str = "") -> dict:
    """Solves C1 x V1 = C2 x V2 for the ONE value left empty. c1 is the stock concentration,
    v1 the volume of stock to use, c2 the final concentration, v2 the final volume. Give the
    other three with units: molar ("10 mM"), mass ("2 mg/mL") or fold ("10X"); volumes like
    "50 uL". Example: how much 10 mM stock makes 50 uL of 200 uM -> c1="10 mM", c2="200 uM",
    v2="50 uL", v1 empty."""
    solve = _blank(c1=c1, v1=v1, c2=c2, v2=v2)
    q = {}
    for name, text in (("c1", c1), ("c2", c2)):
        if name != solve:
            q[name] = _read(text, name, _CONC)
    for name, text in (("v1", v1), ("v2", v2)):
        if name != solve:
            q[name] = _read(text, name, (_VOLUME,))
    if "c1" in q and "c2" in q and _kind(q["c1"]) != _kind(q["c2"]):
        raise ToolError(f"c1 ({_show(q['c1'])}) and c2 ({_show(q['c2'])}) are different kinds "
                        "of concentration — give both molar, both mass per volume, or both fold")

    if solve == "v1":
        q["v1"] = (q["c2"] * q["v2"] / q["c1"]).to(q["v2"].units)
        work = f"V1 = C2 × V2 ÷ C1 = {_show(q['c2'])} × {_show(q['v2'])} ÷ {_show(q['c1'])}"
    elif solve == "v2":
        q["v2"] = (q["c1"] * q["v1"] / q["c2"]).to(q["v1"].units)
        work = f"V2 = C1 × V1 ÷ C2 = {_show(q['c1'])} × {_show(q['v1'])} ÷ {_show(q['c2'])}"
    elif solve == "c1":
        q["c1"] = (q["c2"] * q["v2"] / q["v1"]).to(q["c2"].units)
        work = f"C1 = C2 × V2 ÷ V1 = {_show(q['c2'])} × {_show(q['v2'])} ÷ {_show(q['v1'])}"
    else:
        q["c2"] = (q["c1"] * q["v1"] / q["v2"]).to(q["c1"].units)
        work = f"C2 = C1 × V1 ÷ V2 = {_show(q['c1'])} × {_show(q['v1'])} ÷ {_show(q['v2'])}"
    if q["c2"] > q["c1"] or q["v1"] > q["v2"]:
        raise ToolError(f"the final concentration ({_show(q['c2'])}) would be above the stock "
                        f"({_show(q['c1'])}) — a dilution cannot concentrate")
    diluent = q["v2"] - q["v1"]
    return {
        solve: _show(q[solve]),
        "work": f"{work} = {_show(q[solve])}",
        "recipe": (f"{_show(q['v1'])} of the {_show(q['c1'])} stock + {_show(diluent)} of "
                   f"diluent = {_show(q['v2'])} at {_show(q['c2'])}"),
    }


def _formula_mass(formula: str):
    """(the formula as read, the average molecular weight as a g/mol quantity). A hydrate's
    dot may be written ·, •, * or ."""
    text = str(formula).strip()
    for dot in ("·", "•", "∙", "*"):
        text = text.replace(dot, ".")
    try:
        return text, _Q(Formula(text).mass, "g/mol")
    except Exception as exc:
        raise ToolError(f"cannot read {formula!r} as a chemical formula ({exc}) — write it "
                        "like 'NaCl', 'C4H11NO3' or 'CuSO4.5H2O'") from None


def _molar_mass(formula: str, molecular_weight: str):
    """The molecular weight from `molecular_weight` ("58.44" or "58.44 g/mol") or, when that
    is empty, from `formula`; None when both are."""
    if str(molecular_weight or "").strip():
        raw = str(molecular_weight).strip()
        try:
            q = _Q(raw.translate(_MICRO))
            if not isinstance(q, _Q) or q.dimensionless:      # a bare number is g/mol
                q = _Q(float(q.magnitude if isinstance(q, _Q) else q), "g/mol")
            q = q.to("g/mol")
        except Exception:
            raise ToolError(f"molecular_weight: cannot read {raw!r} — give it in g/mol, like "
                            "'58.44'") from None
        if q.magnitude <= 0:
            raise ToolError(f"molecular_weight must be more than zero, not {raw!r}")
        return q
    if str(formula or "").strip():
        return _formula_mass(formula)[1]
    return None


@register_tool("read_only")
def molar_solution(concentration: str = "", volume: str = "", mass: str = "",
                   formula: str = "", molecular_weight: str = "") -> dict:
    """Mass = concentration x volume x molecular weight, solved for the ONE of concentration,
    volume and mass left empty. Give the other two with units ("150 mM", "500 mL", "4.4 g").
    A molar concentration needs the compound: its formula ("NaCl", "CuSO4.5H2O") or its
    molecular_weight in g/mol; a mass concentration ("2 mg/mL") needs neither. Example: how
    much NaCl for 500 mL of 150 mM -> concentration="150 mM", volume="500 mL", formula="NaCl"."""
    solve = _blank(concentration=concentration, volume=volume, mass=mass)
    mw = _molar_mass(formula, molecular_weight)
    c = _read(concentration, "concentration", (_MOLAR, _MASS_CONC)) if solve != "concentration" else None
    v = _read(volume, "volume", (_VOLUME,)) if solve != "volume" else None
    m = _read(mass, "mass", (_MASS,)) if solve != "mass" else None
    molar = (c is not None and _kind(c) == _MOLAR) or (c is None and mw is not None)
    if molar and mw is None:
        raise ToolError("a molar concentration needs the compound — give its formula or its "
                        "molecular_weight in g/mol")
    f = mw if molar else 1
    mw_part = f" × {_num(mw.magnitude)} g/mol" if molar else ""

    if solve == "mass":
        m = (c * v * f).to("g")
        work = f"mass = C × V{' × MW' if molar else ''} = {_show(c)} × {_show(v)}{mw_part}"
        result = m
    elif solve == "volume":
        v = (m / (c * f)).to("L")
        work = f"V = mass ÷ (C{' × MW' if molar else ''}) = {_show(m)} ÷ ({_show(c)}{mw_part})"
        result = v
    else:
        c = (m / (v * f)).to("M" if molar else "g/mL")
        work = f"C = mass ÷ (V{' × MW' if molar else ''}) = {_show(m)} ÷ ({_show(v)}{mw_part})"
        result = c
    out = {solve: _show(result), "work": f"{work} = {_show(result)}"}
    if molar:
        out["molecular_weight"] = f"{_num(mw.magnitude)} g/mol"
    if solve != "mass":
        return out
    out["recipe"] = (f"weigh {_show(m)}, dissolve in less than {_show(v)}, then bring to "
                     f"{_show(v)}")
    return out


def _factor(text) -> float:
    """A dilution factor written "10", "1:10", "1/10" or "10x" -> 10.0."""
    raw = str(text).strip().lower().rstrip("x× ")
    m = re.fullmatch(r"(?:1\s*[:/]\s*)?(\d+(?:\.\d+)?)", raw)
    if not m or float(m.group(1)) <= 1:
        raise ToolError(f"factor: {text!r} is not a dilution factor above 1 — write it like "
                        "'10' or '1:10' for a ten-fold series")
    return float(m.group(1))


@register_tool("read_only")
def serial_dilution(start: str, factor: str, steps: int, tube_volume: str) -> dict:
    """A serial dilution series: each tube gets a transfer from the tube before it plus
    diluent, so its concentration is the previous one divided by factor. start is the stock
    concentration ("1 mM", "5 mg/mL"); factor is the fold per step ("10" or "1:10", "2" for
    two-fold); steps is how many tubes (1-24); tube_volume is what each tube holds after
    mixing ("1 mL")."""
    c0 = _read(start, "start", _CONC)
    k = _factor(factor)
    try:
        n = int(steps)
    except (TypeError, ValueError):
        raise ToolError(f"steps: {steps!r} is not a whole number of tubes") from None
    if not 1 <= n <= 24:
        raise ToolError(f"steps must be between 1 and 24, not {n}")
    vol = _read(tube_volume, "tube_volume", (_VOLUME,))
    transfer = (vol / k).to(vol.units)
    diluent = vol - transfer
    tubes = [{"tube": i, "concentration": _show(c0 / k ** i)} for i in range(1, n + 1)]
    return {
        "each_tube": (f"{_show(diluent)} of diluent, then {_show(transfer)} from the tube "
                      f"before (tube 1 takes it from the {_show(c0)} stock); mix before the "
                      "next transfer"),
        "tubes": tubes,
        "work": f"transfer = {_show(vol)} ÷ {_num(k)} = {_show(transfer)}; tube n = "
                f"{_show(c0)} ÷ {_num(k)}^n",
        "volumes": (f"every tube but the last ends with {_show(diluent)} after giving "
                    f"{_show(transfer)} to the next; the last keeps {_show(vol)}"),
    }


# Buffers by the name a lab uses: pKa at 25 °C, its change per °C, and what is weighed.
# A titrated buffer is one compound brought to pH with acid or base ("weigh", titrant);
# a two-salt buffer mixes its acid and base forms (masses of both, no titration).
# Values: Good et al. 1966 and the standard biochemistry tables (25 °C, dilute solution).
_BUFFERS = {
    "tris": dict(name="Tris", pka=8.07, dt=-0.028, weigh=("Tris base", 121.14), titrant="HCl"),
    "hepes": dict(name="HEPES", pka=7.48, dt=-0.014, weigh=("HEPES (free acid)", 238.30),
                  titrant="NaOH"),
    "mops": dict(name="MOPS", pka=7.20, dt=-0.015, weigh=("MOPS (free acid)", 209.26),
                 titrant="NaOH"),
    "pipes": dict(name="PIPES", pka=6.76, dt=-0.0085, weigh=("PIPES (free acid)", 302.37),
                  titrant="NaOH"),
    "mes": dict(name="MES", pka=6.10, dt=-0.011, weigh=("MES (free acid)", 195.24),
                titrant="NaOH"),
    "phosphate": dict(name="sodium phosphate", pka=7.20, dt=-0.0028,
                      acid=("NaH2PO4 (monobasic, anhydrous)", 119.98),
                      base=("Na2HPO4 (dibasic, anhydrous)", 141.96)),
    "acetate": dict(name="sodium acetate", pka=4.76, dt=0.0002,
                    acid=("acetic acid", 60.05), base=("sodium acetate (anhydrous)", 82.03)),
}
_ALIASES = {"tris-hcl": "tris", "tris hcl": "tris", "tris base": "tris",
            "sodium phosphate": "phosphate", "na phosphate": "phosphate",
            "sodium acetate": "acetate", "acetic acid": "acetate"}
_ACETIC_DENSITY = 1.049  # g/mL, glacial acetic acid at 25 °C


def _buffer(name: str) -> dict:
    key = re.sub(r"\s+", " ", str(name).strip().lower().replace("buffer", "")).strip()
    key = _ALIASES.get(key, key)
    if key not in _BUFFERS:
        raise ToolError(f"no pKa on file for {name!r} — known buffers: "
                        f"{', '.join(_BUFFERS)}")
    return _BUFFERS[key]


@register_tool("read_only")
def buffer_recipe(buffer: str, ph: float, concentration: str, volume: str,
                  temperature: float = 25.0) -> dict:
    """What to weigh to make a buffer at a pH, from the Henderson-Hasselbalch equation.
    buffer is one of tris, hepes, mops, pipes, mes, phosphate, acetate; ph the target pH;
    concentration the total buffer concentration ("50 mM"); volume how much to make ("1 L");
    temperature the working temperature in °C (Tris shifts with it)."""
    b = _buffer(buffer)
    try:
        ph = float(ph)
        temperature = float(temperature)
    except (TypeError, ValueError):
        raise ToolError("ph and temperature must be numbers") from None
    c = _read(concentration, "concentration", (_MOLAR,))
    v = _read(volume, "volume", (_VOLUME,))
    pka = b["pka"] + b["dt"] * (temperature - 25.0)
    if abs(ph - pka) > 1:
        near = [n for n, o in _BUFFERS.items()
                if abs(ph - (o["pka"] + o["dt"] * (temperature - 25.0))) <= 1]
        raise ToolError(f"pH {_num(ph)} is outside {b['name']}'s useful range (pKa "
                        f"{pka:.2f} ± 1 at {_num(temperature)} °C)"
                        + (f" — buffers that cover it: {', '.join(near)}" if near else ""))
    ratio = 10 ** (ph - pka)            # [base] / [acid]
    base_frac = ratio / (1 + ratio)
    moles = (c * v).to("mol")
    out = {
        "pka": f"{pka:.2f} at {_num(temperature)} °C",
        "work": (f"[base]/[acid] = 10^(pH − pKa) = 10^({_num(ph)} − {pka:.2f}) = "
                 f"{_num(ratio)}; base fraction {_num(base_frac)}; total "
                 f"{_show(c)} × {_show(v)} = {_num(moles.to('mmol').magnitude)} mmol"),
    }
    if "weigh" in b:
        what, mw = b["weigh"]
        grams = moles * _Q(mw, "g/mol")
        # Tris base is titrated DOWN: the acid fraction is protonated by HCl. A free-acid
        # Good's buffer is titrated UP: the base fraction is deprotonated by NaOH.
        need = moles * ((1 - base_frac) if b["titrant"] == "HCl" else base_frac)
        mmol = need.to("mmol").magnitude
        out["recipe"] = (f"dissolve {_show(grams)} {what} in about 80% of {_show(v)} water, "
                         f"adjust to pH {_num(ph)} with {b['titrant']} (about {_num(mmol)} "
                         f"mmol — {_num(mmol)} mL of 1 M {b['titrant']}), then bring to "
                         f"{_show(v)}")
    else:
        (acid, mw_a), (base, mw_b) = b["acid"], b["base"]
        g_acid = (moles * (1 - base_frac) * _Q(mw_a, "g/mol")).to("g")
        g_base = (moles * base_frac * _Q(mw_b, "g/mol")).to("g")
        acid_part = f"{_show(g_acid)} {acid}"
        if acid == "acetic acid":
            acid_part += f" ({_show(_Q(g_acid.magnitude / _ACETIC_DENSITY, 'mL'))} glacial)"
        out["recipe"] = (f"dissolve {acid_part} and {_show(g_base)} {base} in about 80% of "
                         f"{_show(v)} water, check the pH, then bring to {_show(v)}")
    out["note"] = ("Henderson–Hasselbalch ignores ionic strength, so the mixed pH can be off "
                   "by about 0.1 — finish at the pH meter.")
    return out


@register_tool("read_only")
def molecular_weight(formula: str) -> dict:
    """The average molecular weight of a chemical formula in g/mol: "NaCl", "C4H11NO3",
    "CuSO4.5H2O" (a hydrate's dot may be written . or ·)."""
    text, mw = _formula_mass(formula)
    return {"formula": text, "molecular_weight": f"{mw.magnitude:.2f} g/mol"}
