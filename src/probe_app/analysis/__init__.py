"""GUI-independent numerical analysis added from Level 3 onward."""

from probe_app.analysis.fitting import (
    LinearFitError,
    RobustLinearFit,
    robust_linear_fit,
)
from probe_app.analysis.pipeline import CompleteAnalysisResult, analyze_preprocessed
from probe_app.analysis.potential import (
    PotentialAnalysis,
    PotentialCandidate,
    PotentialError,
    estimate_potentials,
)
from probe_app.analysis.preprocessing import (
    PreprocessedSweep,
    PreprocessingError,
    SavitzkyGolaySettings,
    SweepPreview,
    preprocess_sweep,
    safe_savgol_window,
    summarize_sweep,
)
from probe_app.analysis.saturation import (
    SaturationAnalysis,
    SaturationError,
    fit_saturation_regions,
)
from probe_app.analysis.settings import (
    AnalysisSettings,
    PotentialSettings,
    SaturationSettings,
    TemperatureSettings,
)
from probe_app.analysis.temperature import (
    TemperatureAnalysis,
    TemperatureError,
    TemperatureFit,
    fit_panta_temperature,
    panta_current,
)

__all__ = [
    "AnalysisSettings",
    "CompleteAnalysisResult",
    "LinearFitError",
    "PotentialAnalysis",
    "PotentialCandidate",
    "PotentialError",
    "PotentialSettings",
    "PreprocessedSweep",
    "PreprocessingError",
    "RobustLinearFit",
    "SaturationAnalysis",
    "SaturationError",
    "SaturationSettings",
    "SavitzkyGolaySettings",
    "SweepPreview",
    "TemperatureAnalysis",
    "TemperatureError",
    "TemperatureFit",
    "TemperatureSettings",
    "analyze_preprocessed",
    "estimate_potentials",
    "fit_panta_temperature",
    "fit_saturation_regions",
    "panta_current",
    "preprocess_sweep",
    "robust_linear_fit",
    "safe_savgol_window",
    "summarize_sweep",
]
