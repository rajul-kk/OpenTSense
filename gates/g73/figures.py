"""G73 report figures from result.json and runs/main/picard.npz. Usage: python gates/g73/figures.py"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "figures"); os.makedirs(OUT, exist_ok=True)
R = json.load(open(os.path.join(HERE, "result.json")))["rows"]
SURF, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
TOP, BURIED = "#2a78d6", "#eb6834"
BONDS = [("B0_microbump", "Micro-bump"), ("B1_hybrid", "Hybrid"), ("B2_m3dlike", "Monolithic-like")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.labelcolor": MUTED, "axes.edgecolor": GRID, "axes.linewidth": 1,
                     "xtick.color": MUTED, "ytick.color": MUTED, "xtick.major.size": 0, "ytick.major.size": 0, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .8,
                     "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "legend.frameon": False, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left"})


def rows(die):
    return [r for r in R if r["die"] == die]


# Figure 1: DFS against error
fig, ax = plt.subplots(figsize=(6.3, 4))
for die, col, mark, name in (("top", TOP, "o", "Top die"), ("buried", BURIED, "s", "Buried die")):
    ax.scatter([r["dfs"] for r in rows(die)], [100 * r["err"] for r in rows(die)], s=52, c=col, marker=mark, edgecolors=SURF, linewidths=1.5, label=name, zorder=3)
ax.set(xlabel="Degrees of freedom for signal (DFS)", ylabel="Per-die power error (%)", xlim=(0, 10), ylim=(0, 55))
ax.legend(loc="upper right")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "g73_dfs_vs_error.png"), dpi=200); plt.close(fig)

# Figure 2: real against equal prior power, one row per configuration
order = [(b, k) for b, _ in BONDS for k in (8, 16, 32)]
fig, axes = plt.subplots(1, 2, figsize=(6.3, 4.2), sharey=True, sharex=True)
lookup = {(r["bond"], r["K"], r["die"]): r for r in R}
y = np.arange(len(order))[::-1] + np.array([2 * (2 - i // 3) * .45 for i in range(9)])
for ax, key, title in ((axes[0], "dfs", "Real prior power"), (axes[1], "dfs_equal_power", "Equal prior power")):
    ax.set_title(title); ax.grid(axis="y", visible=False)
    for yi, (b, k) in zip(y, order):
        a, c = lookup[(b, k, "top")][key], lookup[(b, k, "buried")][key]
        ax.plot([a, c], [yi, yi], color=GRID, lw=2, zorder=1)
        ax.scatter(a, yi, s=46, c=TOP, marker="o", edgecolors=SURF, linewidths=1.2, zorder=3)
        ax.scatter(c, yi, s=46, c=BURIED, marker="s", edgecolors=SURF, linewidths=1.2, zorder=3)
    ax.set_xlabel("DFS")
axes[0].set_yticks(y, [f"{n}, {k // 2} per die" for _, n in BONDS for k in (8, 16, 32)], fontsize=8.5)
hs = [plt.Line2D([], [], ls="", marker="o", color=TOP, ms=7, label="Top die"), plt.Line2D([], [], ls="", marker="s", color=BURIED, ms=7, label="Buried die")]
fig.legend(handles=hs, loc="lower center", ncol=2)
fig.tight_layout(rect=(0, .06, 1, 1)); fig.savefig(os.path.join(OUT, "g73_equal_power_control.png"), dpi=200); plt.close(fig)

# Figure 3: Picard plot of the buried die with 16 sensors, per bond
Z = np.load(os.path.join(HERE, "runs", "main", "picard.npz"))
fig, axes = plt.subplots(1, 3, figsize=(6.3, 3.3), sharey=True, sharex=True)
for ax, (b, name) in zip(axes, BONDS):
    sv, coef = Z[f"{b}_K16_buried_sv"], Z[f"{b}_K16_buried_coef"]; i = np.arange(1, len(sv) + 1)
    ax.semilogy(i, sv, color=TOP, lw=2, marker="o", ms=4.5, mec=SURF, label="Singular value (whitened gain)")
    ax.semilogy(i, coef, color=BURIED, lw=2, marker="s", ms=4.5, mec=SURF, label="Data coefficient (mean magnitude)")
    ax.axhline(np.sqrt(2 / np.pi), color=MUTED, lw=1, ls="--", zorder=1)          # mean |N(0,1)|: whitened noise alone
    ax.set_title(name); ax.set_xlabel("Mode")
axes[0].text(16, 1.0, "noise level", color=MUTED, fontsize=8, ha="right", va="bottom")
axes[0].set_ylabel("Magnitude")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=2, fontsize=9)
fig.tight_layout(rect=(0, .09, 1, 1)); fig.savefig(os.path.join(OUT, "g73_picard_buried.png"), dpi=200); plt.close(fig)
for k in ("B0_microbump", "B1_hybrid", "B2_m3dlike"):
    print(k, np.round(Z[f"{k}_K16_buried_sv"], 3), np.round(Z[f"{k}_K16_buried_coef"], 3))
