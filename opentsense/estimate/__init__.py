"""Sparse-sensor temperature-field reconstruction: a Gaussian field prior fitted to simulated fields (field_model),
sensor placement (placement), calibrated uncertainty and an out-of-distribution score (calibrate), and a read-only
IC-ThermBench loader with a cross-package check (icthermbench, ood_check)."""
from .field_model import GaussianField, Posterior  # noqa: F401
from . import calibrate, placement  # noqa: F401
