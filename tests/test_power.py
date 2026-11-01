from opentsense.power import asap7_models, workloads

CELL = """module DFFHQNx1_ASAP7_75t_R (QN, D, CLK);
	output QN;
	input D, CLK;
	reg notifier;
	wire delayed_D, delayed_CLK;

	not (int_fwire_d, delayed_D);
	altos_dff (int_fwire_IQN, notifier, delayed_CLK, int_fwire_d, xcr_0);

	// Timing
	specify
		(posedge CLK => (QN+:!D)) = 0;
		$setuphold (posedge CLK, posedge D, 0, 0, notifier,,, delayed_CLK, delayed_D);
	endspecify
endmodule
"""


def test_functional_patch():
    s = asap7_models.functional(CELL)
    assert "delayed" not in s and "specify" not in s
    assert "not (int_fwire_d, D);" in s and "notifier, CLK, int_fwire_d" in s


def test_ibex_reference_checksums():
    # the G30 values, from the same kernels on the host
    assert workloads.ibex_expected() == {0: "00031a38", 1: "e89a564e", 2: "0230e831", 3: "00001d1e"}


def test_tpu_stimulus(tmp_path):
    workloads.tpu_stimulus(tmp_path)
    lines = open(tmp_path / "stim_W1.hex").read().split()
    assert len(lines) == workloads.TPU_CYCLES and all(len(l) == 33 for l in lines)
    (tmp_path / "c.txt").write_text("")
    assert workloads.tpu_check(tmp_path / "c.txt", tmp_path / "ref_W1.json") == (0, 0)
