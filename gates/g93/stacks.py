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
import os

from opentsense.power import dram
from opentsense.stack import floorplan, model

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
BULK = {"silicon": SI, "copper": model.Material(400.0, 3.45e6), "mould": model.Material(0.8, 1.8e6)}  # mould as G93a
HTC = 5.0e4                     # W/(m2 K) on the spreader top, as G93a (ASSUMED for a large cold plate or fan sink)
SPREADER = dict(name="spreader", material="copper", thickness_um=1000, n_sub=10)


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


def make(name, size_um, cell_um, layers, p):
    return model.Stack(name, tuple(map(float, size_um)), grid_for(size_um, cell_um), 300.0, HTC, materials(p),
                       [model.Layer(**l) for l in layers]).validate()


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
    st = make("g93_s1_vcache", ccd.size_um, cell_um, [
        SPREADER, tim(p), die("l3d", S1_TOP_UM, n_sub=6),
        dict(name="hbond", material="oxide_bond", thickness_um=p["hbond_um"],
             regions=[dict(material="hybrid_bond", rect_um=sram)]),
        die("ccd", S1_CCD_UM)], p)
    return st, {"l3d": l3d.power_map(st.grid), "ccd": ccd.power_map(st.grid)}


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
    st = make("g93_s2_hbm", base.size_um, cell_um, [SPREADER, tim(p)] + layers, p)
    return st, hbm_maps(st.grid[::-1], dies, base)


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
    st = make("g93_s4_3tier", tiers[0].size_um, cell_um, layers, p)
    return st, {n: t.power_map(st.grid) for n, t in zip(names, tiers)}


BUILD = {"s1": s1, "s2": s2, "s3": s3, "s4": s4}


def build(name, cell_um, **interfaces):
    model._known("G93 interfaces", interfaces, set(INTERFACES))
    return BUILD[name](cell_um, {**INTERFACES, **interfaces})
