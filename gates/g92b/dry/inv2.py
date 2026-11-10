import re
from opentsense.power import leaklib as L
base = "* inv\n.include /opt/spice/asap7/asap7_tt_osdi.lib\n.options cshunt=1e-15 {opt}\n.include /opt/spice/asap7/cells_R.sp\nVDD VDD 0 0.7\nVA n_A 0 0.7\n{ns}X1 n_A VDD 0 n_Y INVx1_ASAP7_75t_R\n.control\noption temp={T}\ntran 20p 8n\nmeas tran il avg i(vdd) from=7n to=8n\nmeas tran vy avg v(n_Y) from=7n to=8n\n.endc\n.end\n"
for T in (125, 124.99):
    for opt, ns in (("", ""), ("gmin=1e-15", ""), ("method=gear", ""), ("", ".nodeset v(n_Y)=0\n"), ("itl1=1000 itl6=100", ""), ("noopiter", ""), ("gminsteps=20", "")):
        out = L.ngspice("i", base.format(opt=opt, ns=ns, T=T), ("bsimcmg",))
        print(T, opt, ns.strip(), re.findall(r"^(il|vy)\s*=\s*(\S+)", out, re.M), flush=True)
