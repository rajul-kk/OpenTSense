import pytest

from opentsense.power import sdc

HEAD = """create_clock -name core_clock -period 800.0000 [get_ports {clk}]
set_propagated_clock [get_clocks {core_clock}]
create_clock -name vclk_core -period 800.0000
"""
INPUTS = """set_input_delay 160.0000 -clock [get_clocks {vclk_core}] -add_delay [get_ports {a}]
set_input_delay 120.0000 -clock [get_clocks {vclk_core}] -add_delay [get_ports {b}]
"""


def write(tmp_path, text):
    p = tmp_path / "6_final.sdc"
    p.write_text(text)
    return str(p)


def test_input_time_adds_the_input_clock_latency(tmp_path):
    p = write(tmp_path, HEAD + "set_clock_latency 161.7750 [get_clocks {vclk_core}]\n" + INPUTS)
    assert sdc.half_ps(p) == 400
    assert sdc.input_ps(p) == 322           # ceil(161.775 + 160)


def test_missing_latency_is_zero_as_in_sta(tmp_path):
    assert sdc.input_ps(write(tmp_path, HEAD + INPUTS)) == 160


def test_latency_on_another_clock_is_not_used(tmp_path):
    p = write(tmp_path, HEAD + "set_clock_latency 50 [get_clocks {core_clock}]\n" + INPUTS)
    assert sdc.input_ps(p) == 160


@pytest.mark.parametrize("text", [
    HEAD + INPUTS.replace("{vclk_core}] -add_delay [get_ports {b}]", "{core_clock}] -add_delay [get_ports {b}]"),
    HEAD + INPUTS + "set_input_delay 300 [get_ports {c}]\n",                                 # no clock
    HEAD + INPUTS.replace("160.0000 -clock", "-max 160.0000 -clock"),                         # option first
    HEAD + "set_clock_latency -source 161.775 [get_clocks {vclk_core}]\n" + INPUTS,           # not a silent 0
    HEAD + "set_clock_latency 10 [get_clocks {vclk_core}]\nset_clock_latency 20 [get_clocks {vclk_core}]\n" + INPUTS,
    HEAD,                                                                                     # no input delay
    HEAD + "set_clock_latency 161.775 [get_clocks {vclk_core core_clock}]\n" + INPUTS,        # a clock list
    HEAD + INPUTS.replace("{vclk_core}", "{core_clock}"),                                     # propagated port clock
    HEAD.replace("vclk_core -period 800.0000", "vclk_core -period 400.0000") + INPUTS,        # period mismatch
    HEAD + INPUTS.replace("160.0000", "800.0000"),                                            # on the next edge
    HEAD + "set_clock_latency -300 [get_clocks {vclk_core}]\n" + INPUTS,                      # before the edge
    HEAD + "set_propagated_clock [get_clocks {vclk_core}]\n" + INPUTS,                       # propagated virtual
    HEAD.replace("create_clock -name vclk_core -period 800.0000\n", "") + INPUTS,             # input clock undefined
    HEAD + "create_clock -name vclk_core -period 800.0000\n" + INPUTS,                       # defined twice
])
def test_input_time_refuses_what_it_cannot_read(tmp_path, text):
    with pytest.raises(ValueError):
        sdc.input_ps(write(tmp_path, text))


def test_input_time_rounds_a_float_sum_correctly(tmp_path):
    p = write(tmp_path, HEAD + "set_clock_latency 100.1 [get_clocks {vclk_core}]\n"
              + "set_input_delay 59.9 -clock [get_clocks {vclk_core}] -add_delay [get_ports {a}]\n")
    assert sdc.input_ps(p) == 160


def test_negative_latency_and_continuations_are_read(tmp_path):
    p = write(tmp_path, HEAD + "set_clock_latency -12.5 [get_clocks {vclk_core}]\n"
              + "set_input_delay 160 -clock [get_clocks {vclk_core}] \\\n  -add_delay [get_ports {a}]\n"
              + "# create_clock -name old -period 900 [get_ports {clk}]\n")
    assert sdc.half_ps(p) == 400
    assert sdc.input_ps(p) == 148


REAL = """###############################################################################
# Created by write_sdc
###############################################################################
current_design ibex_core
###############################################################################
# Timing Constraints
###############################################################################
create_clock -name core_clock -period 1400.0000 [get_ports {clk_i}]
set_propagated_clock [get_clocks {core_clock}]
create_clock -name vclk_core_clock -period 1400.0000
set_clock_latency 161.7750 [get_clocks {vclk_core_clock}]
set_input_delay 280.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {boot_addr_i[0]}]
set_input_delay 280.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {test_en_i}]
set_output_delay 280.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {data_we_o}]
"""


def test_orfs_write_sdc_excerpt(tmp_path):
    """Lines as G99's Ibex 6_final.sdc has them (vclk_core_clock contains core_clock's name; trailing space)."""
    p = write(tmp_path, REAL)
    assert (sdc.half_ps(p), sdc.input_ps(p)) == (700, 442)


def test_ns_sdc_refused(tmp_path):
    ns = "create_clock -name core_clock -period 8.0000 [get_ports {clk}]\ncreate_clock -name v -period 8.0000\n" \
         "set_input_delay 1.6 -clock [get_clocks {v}] -add_delay [get_ports {a}]\n"
    with pytest.raises(ValueError):
        sdc.half_ps(write(tmp_path, ns))


@pytest.mark.parametrize("text", [HEAD + "create_clock -name c2 -period 800 [get_ports {clk2}]\n",
                                  HEAD.replace("-period 800.0000 [get_ports", "-period [get_ports"),
                                  HEAD.replace("800.0000 [get_ports", "801.0000 [get_ports"),
                                  HEAD.replace("-period 800.0000 [get_ports", "-waveform {0 300} -period 800 [get_ports")])
def test_half_period_refuses_two_port_clocks_or_odd_period(tmp_path, text):
    with pytest.raises(ValueError):
        sdc.half_ps(write(tmp_path, text))
