"""Sparse-sensor temperature-field reconstruction: a Gaussian field prior fitted to simulated fields (field_model),
sensor placement (placement), calibrated uncertainty and an out-of-distribution score (calibrate), causal per-slot
power estimation with plant identification (dynamic), and a read-only IC-ThermBench loader with a cross-package check
(icthermbench, ood_check)."""
from . import calibrate, dynamic, placement  # noqa: F401
from .field_model import GaussianField, Posterior  # noqa: F401
