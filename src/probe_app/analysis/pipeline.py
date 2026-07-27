from __future__ import annotations

from dataclasses import dataclass

from probe_app.analysis.potential import (
    PotentialAnalysis,
    PotentialCandidate,
    PotentialError,
    estimate_potentials,
)
from probe_app.analysis.preprocessing import PreprocessedSweep
from probe_app.analysis.saturation import (
    SaturationAnalysis,
    SaturationError,
    fit_saturation_regions,
)
from probe_app.analysis.settings import AnalysisSettings, PotentialSettings
from probe_app.analysis.temperature import (
    TemperatureAnalysis,
    TemperatureError,
    TemperatureFit,
    fit_panta_temperature,
)
from probe_app.domain.models.analysis_result import (
    AnalysisStage,
    AnalysisStatus,
    MethodOutcome,
    StageResult,
)


@dataclass(frozen=True, slots=True)
class CompleteAnalysisResult:
    """Numerical arrays and typed Level 4–6 results for one explicit run."""

    preprocessed: PreprocessedSweep
    settings: AnalysisSettings
    potential: PotentialAnalysis | None
    saturation: SaturationAnalysis | None
    temperature: TemperatureAnalysis | None
    stage_results: tuple[StageResult, ...]
    status: AnalysisStatus
    message: str = ""


def analyze_preprocessed(
    preprocessed: PreprocessedSweep,
    settings: AnalysisSettings | None = None,
) -> CompleteAnalysisResult:
    """Run Potential → Saturation → Temperature without hiding failures."""

    settings = settings or AnalysisSettings()
    stage_results: list[StageResult] = []
    try:
        potential = estimate_potentials(preprocessed, settings.potential)
    except PotentialError as error:
        message = str(error)
        stage_results.extend(
            (
                StageResult(
                    stage=AnalysisStage.POTENTIAL,
                    status=AnalysisStatus.ERROR,
                    message=message,
                ),
                _blocked_stage(AnalysisStage.SATURATION, "V_fが未確定です"),
                _blocked_stage(AnalysisStage.TEMPERATURE, "Phiと飽和域が未確定です"),
                _blocked_stage(AnalysisStage.QUALITY, "解析入力が未確定です"),
            )
        )
        return CompleteAnalysisResult(
            preprocessed=preprocessed,
            settings=settings,
            potential=None,
            saturation=None,
            temperature=None,
            stage_results=tuple(stage_results),
            status=AnalysisStatus.ERROR,
            message=message,
        )

    stage_results.append(_potential_stage(potential, settings.potential))
    try:
        saturation = fit_saturation_regions(
            preprocessed,
            potential.selected_vf.value_v,
            settings.saturation,
        )
    except SaturationError as error:
        message = str(error)
        stage_results.extend(
            (
                StageResult(
                    stage=AnalysisStage.SATURATION,
                    status=AnalysisStatus.ERROR,
                    message=message,
                ),
                _blocked_stage(AnalysisStage.TEMPERATURE, "飽和域Fitが未確定です"),
                _blocked_stage(AnalysisStage.QUALITY, "飽和域Fitが未確定です"),
            )
        )
        return CompleteAnalysisResult(
            preprocessed=preprocessed,
            settings=settings,
            potential=potential,
            saturation=None,
            temperature=None,
            stage_results=tuple(stage_results),
            status=AnalysisStatus.ERROR,
            message=message,
        )

    stage_results.append(_saturation_stage(saturation))
    temperature, temperature_stage = _temperature_analysis(
        preprocessed,
        potential,
        saturation,
        settings,
    )
    stage_results.append(temperature_stage)
    quality = _quality_stage(saturation, temperature, temperature_stage)
    stage_results.append(quality)
    return CompleteAnalysisResult(
        preprocessed=preprocessed,
        settings=settings,
        potential=potential,
        saturation=saturation,
        temperature=temperature,
        stage_results=tuple(stage_results),
        status=quality.status,
        message=quality.message,
    )


def _potential_stage(
    result: PotentialAnalysis,
    settings: PotentialSettings,
) -> StageResult:
    methods = [
        MethodOutcome(
            method_id="zero_crossing",
            status=result.selected_vf.status,
            message=result.selected_vf.message,
            selected_candidate_id=result.selected_vf.candidate_id,
            manual_override=settings.selected_vf_candidate_id is not None,
            metrics=_metrics(
                candidate_count=float(len(result.vf_candidates)),
                vf_v=result.selected_vf.value_v,
            ),
        )
    ]
    grouped = _phi_candidate_per_method(result)
    for candidate in grouped:
        metrics: dict[str, float] = {
            "candidate_count": float(
                sum(item.method_id == candidate.method_id for item in result.phi_candidates)
            ),
            "phi_v": candidate.value_v,
            "score": candidate.score,
        }
        if candidate.fit_low is not None:
            metrics["fit1_r_squared"] = candidate.fit_low.r_squared
            metrics["fit1_rmse"] = candidate.fit_low.rmse
        if candidate.fit_high is not None:
            metrics["fit2_r_squared"] = candidate.fit_high.r_squared
            metrics["fit2_rmse"] = candidate.fit_high.rmse
        methods.append(
            MethodOutcome(
                method_id=candidate.method_id,
                status=candidate.status,
                message=candidate.message,
                selected_candidate_id=candidate.candidate_id,
                manual_override=(
                    settings.selected_phi_candidate_id == candidate.candidate_id
                ),
                metrics=_metrics(**metrics),
            )
        )
    return StageResult(
        stage=AnalysisStage.POTENTIAL,
        status=result.status,
        methods=tuple(methods),
        message=result.message,
    )


def _saturation_stage(result: SaturationAnalysis) -> StageResult:
    ion = MethodOutcome(
        method_id="ion_saturation_fit",
        status=AnalysisStatus.VALID,
        metrics=_metrics(
            intercept_a=result.ion_fit.intercept,
            isat_i_a=result.isat_i_a,
            r_squared=result.ion_fit.r_squared,
            rmse_a=result.ion_fit.rmse,
            slope_a_per_v=result.ion_fit.slope,
        ),
    )
    electron = MethodOutcome(
        method_id="electron_saturation_fit",
        status=AnalysisStatus.VALID,
        metrics=_metrics(
            intercept_a=result.electron_fit.intercept,
            isat_e_a=result.isat_e_a,
            r_squared=result.electron_fit.r_squared,
            rmse_a=result.electron_fit.rmse,
            slope_a_per_v=result.electron_fit.slope,
        ),
    )
    parameters = MethodOutcome(
        method_id="saturation_parameters",
        status=result.status,
        message=result.message,
        metrics=_metrics(
            isat_e_a=result.isat_e_a,
            isat_i_a=result.isat_i_a,
            k_per_v=result.k_per_v,
            r_ratio=result.r_ratio,
            vf_v=result.vf_v,
        ),
    )
    return StageResult(
        stage=AnalysisStage.SATURATION,
        status=result.status,
        methods=(ion, electron, parameters),
        message=result.message,
    )


def _temperature_analysis(
    preprocessed: PreprocessedSweep,
    potential: PotentialAnalysis,
    saturation: SaturationAnalysis,
    settings: AnalysisSettings,
) -> tuple[TemperatureAnalysis | None, StageResult]:
    fits: list[TemperatureFit] = []
    methods: list[MethodOutcome] = []
    for candidate in _phi_candidate_per_method(potential):
        try:
            fit = fit_panta_temperature(
                preprocessed,
                saturation,
                phi_candidate_id=candidate.candidate_id,
                method_id=candidate.method_id,
                phi_v=candidate.value_v,
                settings=settings.temperature,
            )
        except TemperatureError as error:
            methods.append(
                MethodOutcome(
                    method_id=candidate.method_id,
                    status=AnalysisStatus.ERROR,
                    message=str(error),
                    selected_candidate_id=candidate.candidate_id,
                )
            )
            continue
        fits.append(fit)
        metrics: dict[str, float] = {
            "fit_point_count": float(fit.fit_point_count),
            "k_per_v": saturation.k_per_v,
            "objective_sse_a2": fit.objective,
            "phi_v": fit.phi_v,
            "rmse_a": fit.rmse_a,
            "ti_ev": fit.ti_ev,
        }
        if fit.simple_ti_ev is not None:
            metrics["simple_ti_ev"] = fit.simple_ti_ev
        if fit.relative_simple_difference is not None:
            metrics["simple_relative_difference"] = fit.relative_simple_difference
        methods.append(
            MethodOutcome(
                method_id=fit.method_id,
                status=fit.status,
                message=fit.message,
                selected_candidate_id=fit.phi_candidate_id,
                manual_override=(
                    settings.potential.selected_phi_candidate_id
                    == fit.phi_candidate_id
                ),
                metrics=_metrics(**metrics),
            )
        )

    if not fits:
        message = "利用可能なPhi候補でT_iをFitできませんでした"
        return None, StageResult(
            stage=AnalysisStage.TEMPERATURE,
            status=AnalysisStatus.ERROR,
            methods=tuple(methods),
            message=message,
        )

    selected_id = potential.selected_phi_candidate_id
    if not any(fit.phi_candidate_id == selected_id for fit in fits):
        selected_id = fits[0].phi_candidate_id
    selected = next(fit for fit in fits if fit.phi_candidate_id == selected_id)
    failed = any(method.status is AnalysisStatus.ERROR for method in methods)
    status = (
        AnalysisStatus.REVIEW
        if failed or selected.status is AnalysisStatus.REVIEW
        else AnalysisStatus.VALID
    )
    messages = [selected.message] if selected.message else []
    if failed:
        messages.append("一部のPhi方式はT_i Fitに失敗しました")
    message = " / ".join(messages)
    return (
        TemperatureAnalysis(
            fits=tuple(fits),
            selected_phi_candidate_id=selected_id,
            status=status,
            message=message,
        ),
        StageResult(
            stage=AnalysisStage.TEMPERATURE,
            status=status,
            methods=tuple(methods),
            message=message,
        ),
    )


def _quality_stage(
    saturation: SaturationAnalysis,
    temperature: TemperatureAnalysis | None,
    temperature_stage: StageResult,
) -> StageResult:
    if temperature is None:
        return _blocked_stage(AnalysisStage.QUALITY, "T_i Fitが未確定です")
    selected = temperature.selected_fit
    status = AnalysisStatus.VALID
    messages: list[str] = []
    if saturation.status is AnalysisStatus.BAD:
        status = AnalysisStatus.BAD
        messages.append(saturation.message)
    if selected.status is AnalysisStatus.REVIEW or temperature_stage.partial_success:
        if status is AnalysisStatus.VALID:
            status = AnalysisStatus.REVIEW
        if selected.message:
            messages.append(selected.message)
    return StageResult(
        stage=AnalysisStage.QUALITY,
        status=status,
        methods=(
            MethodOutcome(
                method_id="quality_summary",
                status=status,
                message=" / ".join(messages),
                metrics=_metrics(
                    k_per_v=saturation.k_per_v,
                    r_ratio=saturation.r_ratio,
                    ti_ev=selected.ti_ev,
                ),
            ),
        ),
        message=" / ".join(messages),
    )


def _phi_candidate_per_method(
    result: PotentialAnalysis,
) -> tuple[PotentialCandidate, ...]:
    methods: list[str] = []
    selected: list[PotentialCandidate] = []
    for candidate in result.phi_candidates:
        if candidate.method_id in methods:
            continue
        same_method = tuple(
            item
            for item in result.phi_candidates
            if item.method_id == candidate.method_id
        )
        chosen = next(
            (
                item
                for item in same_method
                if item.candidate_id == result.selected_phi_candidate_id
            ),
            max(same_method, key=lambda item: item.score),
        )
        methods.append(candidate.method_id)
        selected.append(chosen)
    return tuple(selected)


def _blocked_stage(stage: AnalysisStage, message: str) -> StageResult:
    return StageResult(
        stage=stage,
        status=AnalysisStatus.BAD,
        message=message,
    )


def _metrics(**values: float) -> tuple[tuple[str, float], ...]:
    return tuple(sorted(values.items()))
