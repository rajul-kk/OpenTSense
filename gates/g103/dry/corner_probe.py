"""G103 plumbing probe (not scored): G53/G41's leak.py cells at the SS, TT and FF corners of each kit.

IHP: the PDK's `.lib cornerMOSlv.lib mos_<c>` sections. ASAP7: BSIM-CMG cards 7nm_{TT,SS,FF}_160803.pm from
asap7_pdk_r1p7 (commit in /b/asap7_corners/COMMIT), converted by docker/asap7_osdi.py's card() (TT reproduces the
image's card byte for byte). Each deck is leak.py's own, with only the model line changed.

Usage (in opentsense:g75spice, _build mounted at /b): python gates/g103/dry/corner_probe.py <out.json>
"""
import json
import sys

sys.path.insert(0, "/work")
from opentsense.power import leak  # noqa: E402

CORNERS = ("ss", "tt", "ff")
_ngspice = leak.ngspice


def at(corner):
    def run(name, deck, osdi, *a, **k):
        deck = deck.replace(".lib cornerMOSlv.lib mos_tt", f".lib cornerMOSlv.lib mos_{corner}")
        deck = deck.replace(f"{leak.SPICE}/asap7/asap7_tt_osdi.lib", f"/b/asap7_corners/asap7_{corner}_osdi.lib")
        return _ngspice(name, deck, osdi, *a, **k)
    return run


def main(out):
    res = {}
    for c in CORNERS:
        leak.ngspice = at(c)
        res[c] = {"ihp": dict(map(leak.ihp, ["inv_1_A0", "nand2_1_00", "nor2_1_11"])),
                  "asap7": dict(map(leak.asap7, [("INVx1", v) for v in ("R", "L")] + [("NAND2x1", "R")]))}
        print(c, json.dumps({k: {n: v.get(25, v.get("25")) for n, v in d.items()} for k, d in res[c].items()}), flush=True)
    json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
