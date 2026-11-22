"""G93's four consumer-size stacks and their nominal power maps, built from the floorplans in configs/floorplans and
the figures in draft.md. Every number below that is not from a cited source is a stated assumption (ASSUMED) that the
registration fixes or sweeps. Layers are top first (sink on top), as in every OpenTSense stack.

    stacks.build(name, cell_um, **interfaces) -> (Stack, {die: (ny, nx) W})

`interfaces` overrides any key of INTERFACES (layer thickness or area resistance); thickness and k are both derived
from one parameter set per build, so a sweep keeps k = t / R''.

The gated runs use what all three solvers represent: isotropic layers (bond layers at their vertical k), one
convective face; silicon k(T) is set (k_T_exp) and solved with thermal.run.solve_kT. S2's DRAM dies use
power.dram's bank layout (G59), S4 scales zen3_ccd to S4_TIER_W per tier.
"""
import dataclasses
import os

import numpy as np

from opentsense.power import dram
from opentsense.stack import floorplan, model
from opentsense.thermal import electrothermal

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FLP = os.path.join(ROOT, "configs", "floorplans")

SI = model.Material(130.0, 1.63566e6, None, 1.3)     # k(T) exponent 1.3 (draft, realism options)

# Interfaces carry their measured area resistance R'' (m^2 K/W): a bonded layer of thickness t gets k = t / R'', which
# counts the contact resistance a parallel-rule k leaves out (that rule gave 0.05 and 2.9 mm2 K/W here, about 25x and
# 3-5x too low). Sources, both measured, cited via the SMTA 2025 hybrid-bonding review (Nhanced); graded secondary:
#   hybrid Cu/oxide bond ~1.2 mm2 K/W: Oprins et al., ITherm 2016 (imec); 2.49 simulated by Han and Kawano,
#     EPTC 2021, so swept 1.2 to 2.5;
#   micro-bump layer (solder in underfill) 8 to 15 mm2 K/W: Colgan et al., SEMI-THERM 2012 (IBM); 10 here, swept.
#   TIM1 12.5 mm2 K/W (50 um at 4 W/m K, as G93a): ASSUMED, swept 5 to 20 (polymer TIM1; a solder TIM is lower).
#   oxide-to-oxide bond (S1's structural silicon, AMD slide 14): ASSUMED 1.43 mm2 K/W, the 2 um bond layer's oxide
#     at 1.4 W/m K with the interface itself taken as small (TDTR on bonded SiOx, arXiv 2601.03106); swept to 2.9.
# TSVs are not added: copper columns at about 1% of a silicon die's area raise its vertical k by about 2%.
INTERFACES = dict(hbond_um=2, ubump_um=10, tim_um=50,             # ubump_um ASSUMED (bond layer between HBM dies)
                  r_hbond=1.2e-6, r_oxbond=1.43e-6, r_ubump=10e-6, r_tim=12.5e-6)
CV = {"tim": 2.0e6, "hybrid_bond": 1.9e6, "oxide_bond": 1.6e6, "ubump": 1.8e6}
BULK = {"silicon": SI, "copper": model.Material(400.0, 3.45e6), "mould": model.Material(0.8, 1.8e6),  # mould as G93a
        "air": model.Material(0.026, 1.2e3)}          # lid cavity beside the dies (dry air at about 300 K)
SPREADER = dict(name="spreader", material="copper", thickness_um=1000, n_sub=10)

# Package (17 Nov 2026): the spreader is a lid (S1, S2, S4) or a cold-plate base (S3) wider than the dies, and the sink
# is a cooler of stated thermal resistance spread as a uniform coefficient over the spreader top, h = 1 / (R A).
# Before this the spreader was exactly die-sized under h = 5e4 W/(m2 K), which confines lateral spreading to the die
# and, on a 30 mm lid, would be a 0.02 K/W cooler (no real one is). Beside the dies, under the lid: air.
#   lid_um: square lid side. ASSUMED: about 30 mm for desktop-CPU lids (S1, S4); 15 mm for a stand-alone HBM stack (S2).
#     S3 is lidless (an SXM-class module, cold plate on the dies), so its spreader stays the interposer outline.
#   r_sink (K/W): ASSUMED, a large tower or AIO cooler 0.12 (S1, S4); S2 0.5 (its share of a shared plate);
#     S3 a liquid cold plate 0.03. Swept in the registration, like the interfaces.
PACKAGE = {"s1": dict(lid_um=30000, r_sink=0.12), "s2": dict(lid_um=15000, r_sink=0.5),
           "s3": dict(lid_um=None, r_sink=0.03), "s4": dict(lid_um=30000, r_sink=0.12)}

# BEOL (17 Nov 2026, student's decision after goal 11, `sens/`): each die gets an isotropic BEOL layer on its source
# face under its powered silicon, so every solver can carry it. Goal 11 measured +3 to +21 K on buried dies from its
# vertical resistance and at most 0.11 K from lateral anisotropy at 500 um cells. beol_um 10 and beol_k 2 W/(m K):
# ASSUMED, the low middle of the published vertical range 1 to 6 (secondary sources, `sens/beol_board.py`); cv
# ASSUMED. beol_um=0 builds the stacks without it (goal 11's base).
BEOL = dict(beol_um=10.0, beol_k=2.0)
BEOL_CV = 2.0e6

# Leakage against temperature (17 Nov 2026, goal 15): relative leakage of ASAP7 LVT cells re-solved in ngspice at five
# temperatures (sum of the three LVT reference cells, INVx1_L, NAND2x1_L and the third in G92e's leak_ref.json,
# gates/g92e/runs/main/asap7_lvt/leak_ref.json), normalised to 1 at LEAK_T_REF_K: about 3.3%/K near 85 C, doubling
# every 21 K. The share of each block's power that is leakage at LEAK_T_REF_K is ASSUMED and swept (`sens/leak.py`);
# DRAM dies take the same curve (their periphery is logic), also ASSUMED.
LEAK_TEMPS_C = (25.0, 50.0, 75.0, 100.0, 125.0)
LEAK_CURVE = (0.09452, 0.27768, 0.71606, 1.65036, 3.45940)
LEAK_T_REF_K = 358.15


def leakage(P, share):
    """(dynamic maps, leak) for thermal.run.solve_kT: P is the nominal power at LEAK_T_REF_K, of which `share` (one
    value or {die: value}) is leakage on LEAK_CURVE."""
    return electrothermal.map_leakage(P, share, LEAK_T_REF_K, LEAK_TEMPS_C, LEAK_CURVE)


def materials(p):
    """Bulk materials plus each interface at k = t / R'' (an isotropic layer that carries the cited R'')."""
    k = lambda t_um, r: t_um * 1e-6 / r  # noqa: E731
    return {**BULK,
            "tim": model.Material(k(p["tim_um"], p["r_tim"]), CV["tim"]),
            "hybrid_bond": model.Material(k(p["hbond_um"], p["r_hbond"]), CV["hybrid_bond"]),
            "oxide_bond": model.Material(k(p["hbond_um"], p["r_oxbond"]), CV["oxide_bond"]),
            "ubump": model.Material(k(p["ubump_um"], p["r_ubump"]), CV["ubump"])}


def tim(p):
    return dict(name="tim", material="tim", thickness_um=p["tim_um"], n_sub=3)


# S1: V-Cache on a Zen 3 CCD, CCD face down, L3D hybrid-bonded on the thinned CCD back (AMD ISSCC 2022 26.4)
S1_CCD_UM = 50                  # ASSUMED, not published (draft): swept 20 / 50 / 100 in the reported runs
S1_TOP_UM = 350                 # ASSUMED: L3D and structural silicon thickness ("match 2D CCD Z-height")
# S2: HBM3 12-high class, 8 core dies here (draft), base die at the bottom
S2_CORE_UM, S2_TOP_UM, S2_BASE_UM = 30, 100, 60      # 30 um core dies (SK hynix, secondary); top and base ASSUMED
S2_DRAM_W = 1.5                 # ASSUMED per core die: 12 W over 8 dies + 8 W base = 20 W, the low end of 20-32 W
# S3: GH100-class logic beside four S2 stacks on a silicon interposer, mould between
S3_GAP_UM, S3_MARGIN_UM, S3_INTERPOSER_UM = 1000, 500, 100   # ASSUMED
# S4: three CCD-class tiers, the middle one buried
S4_TIER_W = (20.0, 15.0, 10.0)  # ASSUMED top to bottom: 45 W in total, inside the draft's 30-60 W
S4_TIER_UM = 50                 # ASSUMED


def die(name, thickness_um, n_sub=4, regions=(), material="silicon", source_side="bottom"):
    return dict(name=name, die=True, material=material, thickness_um=thickness_um, source_um=2, n_sub=n_sub,
                source_side=source_side, regions=list(regions))


def grid_for(size_um, cell_um):
    """Cells of about cell_um (exact where regions need it: Stack.cells refuses a region off the grid)."""
    return tuple(int(round(s / cell_um)) for s in size_um)


def make(name, size_um, cell_um, layers, p, grid=None):
    """The stack with its sink: h = 1 / (r_sink x spreader area)."""
    htc = 1.0 / (p["r_sink"] * size_um[0] * size_um[1] * 1e-12)
    return model.Stack(name, tuple(map(float, size_um)), grid or grid_for(size_um, cell_um), 300.0, htc, materials(p),
                       [model.Layer(**l) for l in layers]).validate()


def packaged(name, die_size_um, cell_um, layers, P, p):
    """Die-sized `layers` (spreader first) and maps P under a square lid of side p["lid_um"]: every layer below the
    spreader keeps its material (and regions) over the die footprint and is air beside it. The margin is a whole
    number of the die's cells, so the footprint and every region stay on the grid."""
    nx, ny = grid_for(die_size_um, cell_um)
    c = (die_size_um[0] / nx, die_size_um[1] / ny)
    m = [max(0, int(round((p["lid_um"] - s) / 2 / ci))) for s, ci in zip(die_size_um, c)]
    off = (m[0] * c[0], m[1] * c[1])
    foot = [off[0], off[1], *die_size_um]
    out = [layers[0]]
    for l in layers[1:]:
        inner = [[r["rect_um"][0] + off[0], r["rect_um"][1] + off[1], *r["rect_um"][2:]] for r in l.get("regions", [])]
        rest = [dict(material=l["material"], rect_um=r) for r in subtract(foot, inner)]
        out.append({**l, "material": "air", "regions": rest + [dict(material=r["material"], rect_um=q)
                                                               for r, q in zip(l.get("regions", []), inner)]})
    size = (die_size_um[0] + 2 * off[0], die_size_um[1] + 2 * off[1])
    st = make(name, size, cell_um, out, p, grid=(nx + 2 * m[0], ny + 2 * m[1]))
    return st, {d: st.place(v, foot) for d, v in P.items()}


def subtract(rect, holes):
    """Rectangle `rect` minus non-overlapping `holes` inside it, as rectangles: cut at every hole edge, keep the pieces
    no hole covers, and merge neighbours along x within each strip."""
    xs = sorted({rect[0], rect[0] + rect[2], *(h[0] for h in holes), *(h[0] + h[2] for h in holes)})
    ys = sorted({rect[1], rect[1] + rect[3], *(h[1] for h in holes), *(h[1] + h[3] for h in holes)})
    inside = lambda x, y, h: h[0] <= x < h[0] + h[2] and h[1] <= y < h[1] + h[3]  # noqa: E731
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        run = None
        for x0, x1 in zip(xs, xs[1:]):
            free = not any(inside(x0, y0, h) for h in holes)
            if free and run:
                run[2] = x1 - run[0]
            elif free:
                run = [x0, y0, x1 - x0, y1 - y0]
                out.append(run)
            else:
                run = None
    return out


def on_grid(rect, size_um, cell_um):
    """A rectangle snapped to the cell grid (regions must lie on it); the snap moves each edge by under half a cell."""
    c = [s / g for s, g in zip(size_um, grid_for(size_um, cell_um))]
    x0, y0 = round(rect[0] / c[0]) * c[0], round(rect[1] / c[1]) * c[1]
    x1, y1 = round((rect[0] + rect[2]) / c[0]) * c[0], round((rect[1] + rect[3]) / c[1]) * c[1]
    return [x0, y0, x1 - x0, y1 - y0]


def plan(name, **override):
    f = floorplan.load(os.path.join(FLP, f"{name}.yaml"))
    for k, v in override.items():
        setattr(f, k, v)
    return f.validate()


def s1(cell_um, p):
    ccd = plan("zen3_ccd")
    l3d = plan("vcache_l3d")
    # only the L3D is hybrid-bonded; the structural silicon around it is oxide-bonded (AMD ISSCC 2022 26.4, slide 14)
    sram = on_grid(next(b.rect_um for b in l3d.blocks if b.kind == "sram"), ccd.size_um, cell_um)
    g = grid_for(ccd.size_um, cell_um)
    return packaged("g93_s1_vcache", ccd.size_um, cell_um, [
        SPREADER, tim(p), die("l3d", S1_TOP_UM, n_sub=6),
        dict(name="hbond", material="oxide_bond", thickness_um=p["hbond_um"],
             regions=[dict(material="hybrid_bond", rect_um=sram)]),
        die("ccd", S1_CCD_UM)], {"l3d": l3d.power_map(g), "ccd": ccd.power_map(g)}, p)


def hbm_layers(prefix, p, rect=None):
    """S2's dies top first: top core die, 7 core dies, base; ubump layers between. With rect, each die is a silicon
    region in a mould layer (S3)."""
    reg = [dict(material="silicon", rect_um=list(rect))] if rect else []
    mat = "mould" if rect else "silicon"
    out, dies = [], [f"{prefix}d{i}" for i in range(8)] + [f"{prefix}base"]
    for i, d in enumerate(dies):
        th = S2_TOP_UM if i == 0 else S2_BASE_UM if d.endswith("base") else S2_CORE_UM
        out.append(die(d, th, n_sub=2, regions=reg, material=mat))
        if i < len(dies) - 1:
            out.append(dict(name=f"{prefix}ub{i}", material="ubump" if not rect else "mould", thickness_um=p["ubump_um"],
                            regions=[dict(material="ubump", rect_um=list(rect))] if rect else []))
    return out, dies


def hbm_maps(shape, dies, base_plan):
    ny, nx = shape
    P = {d: dram.die_map(shape, 0.3 * S2_DRAM_W, 0.6 * S2_DRAM_W, 0.1 * S2_DRAM_W, seed=i)  # ASSUMED split
         for i, d in enumerate(dies[:-1])}
    P[dies[-1]] = base_plan.power_map((nx, ny))
    return P


def s2(cell_um, p):
    base = plan("hbm3_base")
    layers, dies = hbm_layers("", p)
    g = grid_for(base.size_um, cell_um)
    return packaged("g93_s2_hbm", base.size_um, cell_um, [SPREADER, tim(p)] + layers, hbm_maps(g[::-1], dies, base), p)


def s3(cell_um, p):
    logic, base = plan("gh100_class"), plan("hbm3_base")
    hw, lw = base.size_um[0], logic.size_um[0]
    W = 2 * (S3_MARGIN_UM + hw + S3_GAP_UM) + lw
    H = lw + 2 * S3_MARGIN_UM
    lx, ly = S3_MARGIN_UM + hw + S3_GAP_UM, S3_MARGIN_UM
    sites = [(S3_MARGIN_UM, ly + o) for o in (0, lw - hw)] + [(lx + lw + S3_GAP_UM, ly + o) for o in (0, lw - hw)]
    # four HBM columns share one layer sequence; the logic die spans the whole stack height as silicon
    layers, dies = hbm_layers("h", p, (0, 0, hw, hw))
    for l in layers:
        l["regions"] = ([dict(material=r["material"], rect_um=[x, y, hw, hw]) for x, y in sites for r in l["regions"]]
                        + [dict(material="silicon", rect_um=[lx, ly, lw, lw])])
    layers.append(dict(name="ubump_l", material="mould", thickness_um=p["ubump_um"],
                       regions=[dict(material="ubump", rect_um=[x, y, w, w]) for x, y, w in
                                [(x, y, hw) for x, y in sites] + [(lx, ly, lw)]]))
    layers.append(dict(name="interposer", material="silicon", thickness_um=S3_INTERPOSER_UM, n_sub=4))
    st = make("g93_s3_25d", (W, H), cell_um, [SPREADER, tim(p)] + layers, p)
    one = hbm_maps((int(round(hw / cell_um)),) * 2, dies, base)
    P = {d: sum(st.place(one[d], (x, y, hw, hw)) for x, y in sites) for d in dies}
    P[dies[-1]] = P[dies[-1]] + st.place(logic.power_map((int(round(lw / cell_um)),) * 2), (lx, ly, lw, lw))
    return st, P


def s4(cell_um, p):
    tiers = [plan("zen3_ccd", total_W=w) for w in S4_TIER_W]
    names = ["top", "mid", "bot"]
    layers = [SPREADER, tim(p)]
    for i, n in enumerate(names):
        layers.append(die(n, S4_TIER_UM, n_sub=3))
        if i < 2:
            layers.append(dict(name=f"hbond{i}", material="hybrid_bond", thickness_um=p["hbond_um"]))
    g = grid_for(tiers[0].size_um, cell_um)
    return packaged("g93_s4_3tier", tiers[0].size_um, cell_um, layers,
                    {n: t.power_map(g) for n, t in zip(names, tiers)}, p)


BUILD = {"s1": s1, "s2": s2, "s3": s3, "s4": s4}


def silicon(st, layer):
    """The layer's silicon rectangles: its regions of silicon, or the whole outline if its base is silicon."""
    if layer.material == "silicon":
        return [(0.0, 0.0, *st.size_um)]
    return [r.rect_um for r in layer.regions if r.material == "silicon"]


def powered(st, layer, P):
    """The die layer's silicon rectangles that carry this die's power (S3: the logic die's silicon runs through
    every HBM layer but is powered only on hbase, so it gets one BEOL layer, not nine)."""
    out = []
    for rect in silicon(st, layer):
        j0, j1, i0, i1 = st.cells(rect)
        if float(np.asarray(P[layer.name])[i0:i1, j0:j1].sum()) > 0:
            out.append(rect)
    return out


def with_beol(st, P, beol_um, k_v, k_l=None, cv=BEOL_CV):
    """A copy of `st` with a BEOL layer on each die's source face (k_l None: isotropic). A die layer whose base is
    silicon gets BEOL over its whole outline; a die layer of regions gets it only over its powered silicon, so
    another die's silicon running through the layer (S3's logic die under the HBM stacks) stays silicon."""
    st = dataclasses.replace(st, materials={**st.materials, "beol": model.Material(k_v, cv, k_l)})
    layers = []
    for l in st.layers:
        beol = None
        if l.die:
            if l.material == "silicon":
                beol = model.Layer(f"{l.name}_beol", "beol", beol_um, n_sub=1)
            else:
                # the die layer's own regions, with its powered silicon turned to BEOL: unpowered silicon running
                # through the layer (S3's logic die under the HBM stacks) stays silicon, not the layer's base mould
                on = powered(st, l, P)
                beol = model.Layer(f"{l.name}_beol", l.material, beol_um, n_sub=1,
                                   regions=[model.Region("beol" if r.material == "silicon" and r.rect_um in on
                                                         else r.material, r.rect_um) for r in l.regions])
        if beol and l.source_side == "top":
            layers.append(beol)
        layers.append(l)
        if beol and l.source_side != "top":
            layers.append(beol)
    return dataclasses.replace(st, layers=layers).validate()


def build(name, cell_um, **params):
    """params override INTERFACES, BEOL and the stack's PACKAGE entry (lid_um, r_sink)."""
    model._known("G93 parameters", params,
                 set(INTERFACES) | set(BEOL) | {"r_sink"} | ({"lid_um"} if PACKAGE[name]["lid_um"] else set()))
    p = {**INTERFACES, **BEOL, **PACKAGE[name], **params}
    st, P = BUILD[name](cell_um, p)
    if p["beol_um"] > 0:
        st = with_beol(st, P, p["beol_um"], p["beol_k"])
    return st, P
