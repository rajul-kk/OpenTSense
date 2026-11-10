import re
from opentsense.power import leaklib as L
base = "* inv\n.include /opt/spice/asap7/asap7_tt_osdi.lib\n{opt}\n.include /opt/spice/asap7/cells_R.sp\nVDD VDD 0 0.7\nVA n_A 0 {a}\nX1 n_A VDD 0 n_Y INVx1_ASAP7_75t_R\n.control\n{ctl}\n.endc\n.end\n"
def run(opt, a, ctl):
    out = L.ngspice("i", base.format(opt=opt, a=a, ctl=ctl), ("bsimcmg",))
    return re.findall(r"^(\w+)\s*=\s*(\S+)", out, re.M)
for T in (25, 100, 110, 120, 125):
    for opt in ("", ".options cshunt=1e-15"):
        print(T, opt or "none", "op:", run(opt, 0.7, f"option temp={T}\nop\nprint i(vdd) v(n_Y)"), "tran:", run(opt, 0.7, f"option temp={T}\ntran 20p 8n\nmeas tran il avg i(vdd) from=7n to=8n\nmeas tran vy avg v(n_Y) from=7n to=8n"))
print("fresh-sequence (25 then 125, op):", run("", 0.7, "option temp=25\nop\nprint i(vdd)\noption temp=125\nop\nprint i(vdd) v(n_Y)"))
