"""DIY material estimator for a gable-roof barndominium (spec section 6).

Quantities only, no prices: material prices swing too much by region and
month to bake in. Every rule of thumb used is returned in `assumptions` so the
owner-builder can see, and argue with, how each number was reached.

Geometry: rectangular footprint W x L, symmetric gable roof running the
length of the building, eave height H, roof pitch P (rise per 12 in of run).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

FOAM_DEFAULTS = {"closed_cell": (2.0, 3.0), "open_cell": (3.5, 5.5)}  # (walls, roof) inches


@dataclass
class EstimateInput:
    width_ft: float
    length_ft: float
    eave_height_ft: float = 14.0
    roof_pitch: float = 3.0
    overhang_ft: float = 1.0
    living_sqft: float | None = None  # defaults to the whole footprint
    ceiling_height_ft: float = 10.0
    slab_thickness_in: float = 4.0
    grade_beam: bool = True
    grade_beam_width_in: float = 12.0
    grade_beam_depth_in: float = 24.0
    rebar_spacing_in: float = 18.0
    insulation: Literal["closed_cell", "open_cell"] = "closed_cell"
    wall_foam_in: float | None = None
    roof_foam_in: float | None = None
    framing: Literal["steel", "wood"] = "wood"
    stud_spacing_in: float = 16.0
    interior_wall_lf_per_sqft: float = 0.11
    frame_exterior_walls: bool = True
    panel_coverage_in: float = 36.0
    waste_pct: float = 10.0


@dataclass
class Line:
    item: str
    qty: float
    unit: str
    note: str = ""


@dataclass
class EstimateResult:
    summary: dict
    sections: dict[str, list[Line]] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)


def _up(x: float, step: float = 1.0) -> float:
    """Round up to the next `step` (avoids float fuzz like 10.0000001 -> 11)."""
    v = math.ceil(round(x / step, 6)) * step
    return int(v) if step >= 1 else round(v, 2)


def estimate(inp: EstimateInput) -> EstimateResult:
    W, L, H, P, oh = inp.width_ft, inp.length_ft, inp.eave_height_ft, inp.roof_pitch, inp.overhang_ft
    waste = 1 + inp.waste_pct / 100
    footprint = W * L
    living = min(inp.living_sqft or footprint, footprint)
    shop = footprint - living
    cov_ft = inp.panel_coverage_in / 12

    # ---------------- geometry
    run = W / 2
    rise = run * P / 12
    rafter = run * math.sqrt(1 + (P / 12) ** 2)  # eave to ridge, along the slope
    perimeter = 2 * (W + L)
    gable_area = 0.5 * W * rise  # one triangle
    wall_area = perimeter * H + 2 * gable_area
    roof_area = 2 * (rafter + oh) * (L + 2 * oh)
    roof_area_inside = 2 * rafter * L  # underside of roof deck, for foam

    a: list[str] = [
        f"Gable roof: rise {rise:.2f} ft over a {run:g} ft run at {P:g}/12; slope length {rafter:.2f} ft per side.",
        f"Overhang {oh:g} ft at eaves and gables; panel coverage {inp.panel_coverage_in:g} in (PBR/R-panel style).",
        f"Waste factor {inp.waste_pct:g}% applied to sheet goods, concrete and rebar; not to counts of panels.",
        "Door and window openings are NOT deducted, so panel and foam numbers run slightly high on purpose.",
    ]

    # ---------------- 1. slab & foundation
    slab_cf = footprint * inp.slab_thickness_in / 12
    beam_cf = 0.0
    if inp.grade_beam:
        beam_cf = (
            perimeter * (inp.grade_beam_width_in / 12) * max(inp.grade_beam_depth_in - inp.slab_thickness_in, 0) / 12
        )
    concrete_cy = (slab_cf + beam_cf) / 27
    bars_along_l = math.floor(W * 12 / inp.rebar_spacing_in) + 1
    bars_along_w = math.floor(L * 12 / inp.rebar_spacing_in) + 1
    rebar_lf = bars_along_l * L + bars_along_w * W + (4 * perimeter if inp.grade_beam else 0)
    rebar_lf *= waste
    foundation = [
        Line(
            "Concrete (slab" + (" + perimeter grade beam" if inp.grade_beam else "") + ")",
            _up(concrete_cy * waste, 0.5),
            "cu yd",
            f"slab {slab_cf / 27:.1f} yd + beam {beam_cf / 27:.1f} yd before waste",
        ),
        Line(
            "#4 rebar",
            _up(rebar_lf / 20),
            "20-ft sticks",
            f"{inp.rebar_spacing_in:g} in grid both ways"
            + ("; 4 continuous bars in the grade beam" if inp.grade_beam else ""),
        ),
        Line("Rebar chairs", _up(footprint / 9), "each", "about 1 per 9 sq ft"),
        Line("Vapor barrier (10 mil)", _up(footprint * 1.15), "sq ft", "+15% for laps and turn-up at the edges"),
    ]
    a.append(
        f"Slab {inp.slab_thickness_in:g} in thick"
        + (
            f"; grade beam {inp.grade_beam_width_in:g} in wide x {inp.grade_beam_depth_in:g} in deep (incl. slab)."
            if inp.grade_beam
            else "; no thickened edge."
        )
    )

    # ---------------- 2. exterior shell (metal)
    roof_panels_per_side = math.ceil((L + 2 * oh) / cov_ft)
    side_panels_per_side = math.ceil(L / cov_ft)
    end_panels_per_end = math.ceil(W / cov_ft)
    endwall_lf = 2 * (W * H + gable_area) / cov_ft  # total panel length both gable ends
    shell = [
        Line(
            "Roof panels",
            roof_panels_per_side * 2,
            "panels",
            f"{roof_panels_per_side} per side, cut length {_ft_in(rafter + oh)}",
        ),
        Line("Roof area", round(roof_area), "sq ft", "including overhangs"),
        Line("Sidewall panels", side_panels_per_side * 2, "panels", f"{side_panels_per_side} per side at {_ft_in(H)}"),
        Line(
            "Endwall panels",
            end_panels_per_end * 2,
            "panels",
            f"{end_panels_per_end} per end, cut to the gable slope; about {_up(endwall_lf)} LF total",
        ),
        Line("Wall area", round(wall_area), "sq ft", "both sidewalls + both gable ends"),
        Line("Ridge cap", _up(L + 2 * oh), "LF", ""),
        Line("Eave trim", _up(2 * (L + 2 * oh)), "LF", ""),
        Line("Rake / gable trim", _up(4 * (rafter + oh)), "LF", ""),
        Line("Outside corner trim", _up(4 * H), "LF", ""),
        Line("Base trim", _up(perimeter), "LF", ""),
        Line(
            "Panel screws",
            _up((roof_area + wall_area) * 0.8 * waste, 250),
            "each",
            "about 80 per 100 sq ft; buy in 250-packs",
        ),
        Line(
            "Closure strips",
            _up(2 * (L + 2 * oh) * 2 + perimeter),
            "LF",
            "outside closures at the ridge, inside closures at the eaves, plus base",
        ),
    ]

    # ---------------- 3. spray foam insulation
    wall_in, roof_in = FOAM_DEFAULTS[inp.insulation]
    wall_in = inp.wall_foam_in or wall_in
    roof_in = inp.roof_foam_in or roof_in
    wall_bf = wall_area * wall_in
    roof_bf = roof_area_inside * roof_in
    foam = [
        Line(
            f"Spray foam, walls ({inp.insulation.replace('_', ' ')})",
            _up(wall_bf * waste, 100),
            "board ft",
            f"{round(wall_area)} sq ft at {wall_in:g} in",
        ),
        Line(
            f"Spray foam, roof deck ({inp.insulation.replace('_', ' ')})",
            _up(roof_bf * waste, 100),
            "board ft",
            f"{round(roof_area_inside)} sq ft at {roof_in:g} in",
        ),
    ]
    a.append("Foam covers the whole building envelope, shop included; drop the shop share if it stays unconditioned.")
    a.append("1 board foot = 1 sq ft at 1 in thick. Contractors usually quote foam per board foot.")

    # ---------------- 4. interior framing (living area)
    living_depth = living / W
    ext_lf_living = 2 * (W + living_depth) if shop > 0 else perimeter
    int_lf = living * inp.interior_wall_lf_per_sqft
    framed_lf = int_lf + (ext_lf_living if inp.frame_exterior_walls else 0)
    studs = math.ceil(framed_lf * 12 / inp.stud_spacing_in * 1.15)
    stud_word = "Steel studs" if inp.framing == "steel" else "Wood studs (2x4)"
    plate_word = "Steel track" if inp.framing == "steel" else "Plates (2x4, bottom + double top)"
    plate_lf = framed_lf * (2 if inp.framing == "steel" else 3)
    framing = [
        Line("Interior partition walls", _up(int_lf), "LF", f"{inp.interior_wall_lf_per_sqft:g} LF per living sq ft"),
        Line(
            stud_word,
            studs,
            "each",
            f"{inp.stud_spacing_in:g} in on center at {_ft_in(inp.ceiling_height_ft)}, +15% for corners/openings",
        ),
        Line(plate_word, _up(plate_lf * waste), "LF", ""),
    ]
    if inp.frame_exterior_walls:
        a.append("Living-area exterior walls get a stud wall inside the steel shell for drywall, wiring and foam.")
    if shop > 0:
        a.append(
            f"Living area {living:g} sq ft spans the full {W:g} ft width ({living_depth:.1f} ft deep); "
            f"shop {shop:g} sq ft is left unfinished. The wall between them is counted as exterior wall."
        )
    if inp.framing == "steel":
        a.append("Steel studs: every wire hole needs a grommet (see the electrical rough-in guide).")

    # ---------------- 5. drywall (living area)
    walls_dw = ext_lf_living * inp.ceiling_height_ft + int_lf * inp.ceiling_height_ft * 2
    ceiling_dw = living
    dw_area = (walls_dw + ceiling_dw) * waste
    drywall = [
        Line("Drywall, walls + ceilings", round(dw_area), "sq ft", ""),
        Line("Drywall sheets (4x12)", _up(dw_area / 48), "sheets", "use 5/8 in on ceilings if trusses are 24 in o.c."),
        Line("Joint compound (4.5 gal box)", _up(dw_area / 450), "boxes", "about 1 box per 450 sq ft"),
        Line("Drywall screws", _up(dw_area / 1000 * 5, 1), "lb", "about 5 lb per 1,000 sq ft"),
    ]

    return EstimateResult(
        summary={
            "footprint_sqft": round(footprint),
            "living_sqft": round(living),
            "shop_sqft": round(shop),
            "concrete_cy": foundation[0].qty,
            "metal_panel_area_sqft": round(roof_area + wall_area),
            "spray_foam_board_ft": foam[0].qty + foam[1].qty,
            "drywall_sheets": drywall[1].qty,
        },
        sections={
            "Slab & foundation": foundation,
            "Exterior shell (metal)": shell,
            "Spray foam insulation": foam,
            "Interior framing": framing,
            "Drywall": drywall,
        },
        assumptions=a,
    )


def _ft_in(feet: float) -> str:
    inches = math.ceil(round(feet * 12, 6))
    return f"{inches // 12}' {inches % 12}\""
