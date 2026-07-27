# Level 4–6 analysis numerical and interaction contract

## Scope

One explicitly selected `Sweep` is analyzed in this order:

```text
Sweep
  → Savitzky–Golay preprocessing
  → V_f / Phi candidates
  → ion and electron saturation fits
  → PANTA T_i model fits
  → quality result
```

Changing a workspace tab, candidate combo box, or numeric field must not start any of these calculations.
The pipeline runs only when the user presses the Level 4–6 analysis button.

## Numerical defaults

| Item | Default |
|---|---:|
| log Fit1 | 10–15 V |
| log Fit2 | 20–50 V |
| Phi candidate search | 10–20 V |
| ion saturation fit | -35–-15 V |
| electron saturation fit | 20–50 V |
| T_i bounds | 0.1–10 eV |
| T_i fit window | `[Phi - 0.1, Phi]` V |
| robust clipping | 2.5 MAD-sigma, at most 6 iterations |

`robust_linear_fit` uses a scale-aware floating-point tolerance when MAD is almost zero. This keeps all
numerically identical inliers while still rejecting a large isolated residual.

## Potential contract

- `V_f` candidates are found from adjacent current samples with opposite signs or an exact zero.
- Each crossing is linearly interpolated in the original voltage order. Current sorting is not used.
- The automatic `V_f` is the candidate below and closest to the selected `Phi` when available.
- The log candidate fits `log10(I)` only where filtered current is positive.
- Both log regions require at least 8 points and use robust linear fits.
- The intersection is rejected when the lines are effectively parallel or outside the configured Phi range.
- Derivative candidates are positive local maxima in the configured range, ordered by height and de-duplicated
  within 0.25 V.
- Candidate IDs are stable inputs to the analysis revision and may be manually selected.

## Saturation contract

Filtered current is fitted independently in the ion and electron ranges:

```text
I(V) = m V + c
```

Both lines are evaluated at the selected `V_f`:

```text
I_sat,i = abs(m_i V_f + c_i)
I_sat,e = abs(m_e V_f + c_e)
R       = I_sat,e / I_sat,i
K       = abs(m_e / I_sat,e)
```

`R` outside 0.2–5.0 or `K` outside 0–0.2 V^-1 is retained and marked `bad`; it is not silently clipped.

## Temperature contract

For each available Phi method:

```text
I_model(V; T_i)
  = I_sat,i [R {1 + K(V - V_f)} - exp((Phi - V) / T_i)]
```

Only `T_i` varies. `Phi`, `V_f`, `I_sat,i`, `R`, and `K` are fixed from preceding stages.
`scipy.optimize.minimize_scalar(method="bounded")` minimizes the current-space sum of squared residuals.
At least 5 finite samples are required in the fit window. The result includes:

- fitted `T_i`, objective value, RMSE, and point count;
- a deterministic objective grid for visual inspection;
- a simple derivative-based estimate when available;
- review status for a boundary solution, flat objective, or large model/simple disagreement.

## Failure and partial-success contract

- Every stage produces one `StageResult`.
- A potential failure blocks saturation, temperature, and quality with explicit messages.
- A saturation failure blocks temperature and quality.
- A failure in one Phi temperature method does not erase a successful method; the stage is marked for review.
- `not_run`, `valid`, `review`, `bad`, `error`, and stale revision states remain distinguishable in downstream
  projections.

## Automated coverage

`tests/unit/test_level4_to_6_analysis.py` fixes:

- robust-fit behavior with a large isolated outlier;
- zero crossing, log intersection, and derivative peak candidates;
- `I_sat,i/e`, `R`, and `K` on a deterministic piecewise curve;
- recovery of a known synthetic PANTA `T_i`;
- ordered pipeline stage output and revision-setting stability.

`tests/unit/test_fit_analysis_panel.py` fixes the explicit-run interaction: editing and candidate selection do
not emit a calculation request, while pressing the run button emits exactly one typed `AnalysisSettings`.

The full regression gate is:

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

## Manual macOS check

1. Open a measurement folder and select current and sweep-voltage roles.
2. Select a Sweep and open the Analysis workspace.
3. Confirm that the workspace shows `未実行` before pressing the analysis button.
4. Press the Level 4–6 analysis button and inspect `V_f`, `Phi`, saturation lines, PANTA curve, and objective.
5. Select another candidate or change a range. Confirm that the prior result becomes pending but does not change.
6. Press the button again and confirm that the displayed result and revision update together.
7. Switch among the four top-level workspaces and confirm that no analysis begins automatically.
