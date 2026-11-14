# A finished ORFS ASAP7 design with routed parasitics, for OpenSTA in the ORFS image.
# env: RES (dir with 6_final.{odb,sdc,spef}), CORNER (library corner tag: TT, FF or SS), VTS (e.g. "RVT" or "RVT LVT SLVT")
set L /OpenROAD-flow-scripts/flow/platforms/asap7/lib/NLDM
read_db $::env(RES)/6_final.odb
foreach vt $::env(VTS) {
  foreach f [glob $L/asap7sc7p5t_{AO,INVBUF,OA,SIMPLE}_${vt}_$::env(CORNER)_nldm_2*.lib.gz $L/asap7sc7p5t_SEQ_${vt}_$::env(CORNER)_nldm_2*.lib] { read_liberty $f }
}
read_sdc $::env(RES)/6_final.sdc
read_spef $::env(RES)/6_final.spef
