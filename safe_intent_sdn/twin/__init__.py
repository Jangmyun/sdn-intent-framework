"""Digital Twin execution core for Experiment 3 (Twin decision fidelity, RQ3).

This package ports the working Mininet+ONOS twin from the sibling project
``sdn-xai-pipeline`` into this repository so that E3 can measure how well the
twin's automated pass/fail verdict matches the real behavioral outcome of an
emulated deployment (see paper/experiment_protocol/e3_rationale.md).

Everything here requires Linux + root + Mininet + a reachable ONOS controller at
run time, so Mininet is imported lazily *inside* the build/verify functions --
importing this package on a non-Linux / non-root host (e.g. in CI) is safe and
only the pure helpers are exercised there.
"""

from __future__ import annotations

from .onos_client import OnosClient, OnosError
from .twin_verifier import TwinResult, TwinVerifier

__all__ = ["OnosClient", "OnosError", "TwinResult", "TwinVerifier"]
