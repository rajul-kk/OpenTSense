"""Process-corner kits (G103): a corner kit is its TT kit with only the device models at the corner."""
import os
import re
import shutil
import subprocess

import pytest

from opentsense.power import leaklib
from opentsense.power.leak import CORNERS


@pytest.mark.parametrize("base", ["ihp", "asap7", "asap7_lvt"])
@pytest.mark.parametrize("c", [c for c in CORNERS if c != "tt"])
def test_corner_kit_changes_only_the_models_to_that_corner(base, c):
    tt, k = leaklib.KITS[base], leaklib.KITS[f"{base}@{c}"]
    assert {n: v for n, v in k.items() if n != "models"} == {n: v for n, v in tt.items() if n != "models"}
    assert "_tt" not in re.sub(r"[^\w]", " ", k["models"]).replace("cshunt", "")
    assert k["models"] == tt["models"].replace("_tt", f"_{c}")      # same line, corner tokens only (no _tt in paths)


@pytest.mark.skipif(not shutil.which("docker"), reason="needs the opentsense:g103 image")
def test_every_corner_model_file_is_in_the_image():
    files = [f"/opt/spice/asap7/asap7_{c}_osdi.lib" for c in CORNERS]
    cmd = ["docker", "run", "--rm", "opentsense:g103", "sh", "-c",
           " && ".join([f"test -s {f}" for f in files] +
                       [f"grep -qi 'lib mos_{c}' /opt/spice/ihp/models/cornerMOSlv.lib" for c in CORNERS] +
                       [f"grep -qi 'lib dio_{c}' /opt/spice/ihp/models/cornerDIO.lib" for c in CORNERS])]
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    assert r.returncode == 0, r.stderr
