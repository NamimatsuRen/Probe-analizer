from __future__ import annotations

import math
from dataclasses import dataclass


def _validate_range(name: str, lower: float, upper: float) -> None:
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ValueError(f"{name} must contain finite values")
    if upper <= lower:
        raise ValueError(f"{name} upper bound must be greater than its lower bound")


@dataclass(frozen=True, slots=True)
class PotentialSettings:
    """Ranges and explicit candidate selections for V_f and Phi."""

    log_fit1_min_v: float = 10.0
    log_fit1_max_v: float = 15.0
    log_fit2_min_v: float = 20.0
    log_fit2_max_v: float = 50.0
    phi_search_min_v: float = 10.0
    phi_search_max_v: float = 20.0
    selected_vf_candidate_id: str | None = None
    selected_phi_candidate_id: str | None = None

    def __post_init__(self) -> None:
        _validate_range(
            "log_fit1",
            self.log_fit1_min_v,
            self.log_fit1_max_v,
        )
        _validate_range(
            "log_fit2",
            self.log_fit2_min_v,
            self.log_fit2_max_v,
        )
        _validate_range(
            "phi_search",
            self.phi_search_min_v,
            self.phi_search_max_v,
        )


@dataclass(frozen=True, slots=True)
class SaturationSettings:
    """Voltage ranges and quality bounds for saturation fits."""

    ion_min_v: float = -35.0
    ion_max_v: float = -15.0
    electron_min_v: float = 20.0
    electron_max_v: float = 50.0
    r_min: float = 0.2
    r_max: float = 5.0
    k_min_per_v: float = 0.0
    k_max_per_v: float = 0.2

    def __post_init__(self) -> None:
        _validate_range("ion_range", self.ion_min_v, self.ion_max_v)
        _validate_range(
            "electron_range",
            self.electron_min_v,
            self.electron_max_v,
        )
        _validate_range("r_quality_range", self.r_min, self.r_max)
        _validate_range(
            "k_quality_range",
            self.k_min_per_v,
            self.k_max_per_v,
        )


@dataclass(frozen=True, slots=True)
class TemperatureSettings:
    """Bounded one-parameter PANTA model fit settings."""

    min_ti_ev: float = 0.1
    max_ti_ev: float = 10.0
    fit_window_v: float = 0.1
    minimum_points: int = 5
    objective_grid_points: int = 161

    def __post_init__(self) -> None:
        _validate_range("ti_bounds", self.min_ti_ev, self.max_ti_ev)
        if not math.isfinite(self.fit_window_v) or self.fit_window_v <= 0:
            raise ValueError("fit_window_v must be finite and positive")
        if self.minimum_points < 3:
            raise ValueError("minimum_points must be at least 3")
        if self.objective_grid_points < 21:
            raise ValueError("objective_grid_points must be at least 21")


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    """All Level 4–6 settings used by one explicit analysis run."""

    potential: PotentialSettings = PotentialSettings()
    saturation: SaturationSettings = SaturationSettings()
    temperature: TemperatureSettings = TemperatureSettings()

    def as_revision_settings(self) -> tuple[tuple[str, str], ...]:
        """Return a stable, sorted representation for AnalysisInputRevision."""

        values = {
            "electron_max_v": self.saturation.electron_max_v,
            "electron_min_v": self.saturation.electron_min_v,
            "ion_max_v": self.saturation.ion_max_v,
            "ion_min_v": self.saturation.ion_min_v,
            "log_fit1_max_v": self.potential.log_fit1_max_v,
            "log_fit1_min_v": self.potential.log_fit1_min_v,
            "log_fit2_max_v": self.potential.log_fit2_max_v,
            "log_fit2_min_v": self.potential.log_fit2_min_v,
            "phi_search_max_v": self.potential.phi_search_max_v,
            "phi_search_min_v": self.potential.phi_search_min_v,
            "selected_phi_candidate_id": (
                self.potential.selected_phi_candidate_id or "auto"
            ),
            "selected_vf_candidate_id": (
                self.potential.selected_vf_candidate_id or "auto"
            ),
            "ti_fit_window_v": self.temperature.fit_window_v,
            "ti_max_ev": self.temperature.max_ti_ev,
            "ti_min_ev": self.temperature.min_ti_ev,
        }
        return tuple(
            sorted(
                (key, value if isinstance(value, str) else format(value, ".12g"))
                for key, value in values.items()
            )
        )
