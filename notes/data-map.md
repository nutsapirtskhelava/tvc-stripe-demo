# Data map — AIM TvC Study

Read-only survey of what's in this project folder. Nothing in the source data has been modified.

## Files

| File | Type | Rows/sheets | Notes |
|---|---|---|---|
| `AIM TvC Subjects Deidentified (Amblyopia).csv` | demographics | 7 subjects, 25 columns | Referring Provider / Date of Testing / Notes excluded from analysis (see CLAUDE.md) |
| `AIM TvC Subjects Deidentified (Control 2).csv` | demographics | 12 subjects, 25 columns (+3 empty `Unnamed` trailing columns) | same exclusions |
| `amblyopia_control_OD_OS_all_subjects-2.xlsx` | TvC task output | sheets: `AllData`, `Control_OD`, `Control_OS`, `Amblyopia_OD`, `Amblyopia_OS`, `Notes` (excluded) | one row per chart (1-5) + a "Final" summary row (ChartNum=6), per subject per eye |
| `analyze_WF_internal_noise.m` | existing analysis script | — | MATLAB; group stats, mixed model, Fig1-4 |
| `plot_tvc_curves.py` | new analysis script | — | Python; derives theoretical TvC curves from fitted IN/Psi |
| `results/` | outputs | 5 figures + `WF_IN_results.xlsx` | group-level only, safe to keep in git |

## Subject counts

- Amblyopia CSV: 7 subjects (IDs 24, 25, 32, 35, 36, 37, 41)
- Control CSV: 12 subjects (IDs 26-43)
- xlsx TvC data: 12 control subjects (matches CSV exactly), but only **6** amblyopic subjects

## Subject exclusions (per user, 2026-11-24)

Subjects **26** and **32** are excluded completely from all analyses going forward.

## Known inconsistencies (reported, not fixed)

1. **Psi pinned at its upper bound (2.0)** in 7/216 rows, including a "Final" row for subject 35 OS — likely an unreliable fit, not fixed.

## Clarified (not actual data issues)

- Dates embedded in Stereoacuity / Worth 4 dot fields (e.g. "07/23/2026") record the last clinic
  visit documentation date, not an entry error — ignore the date, use the measurement.
- "Stereo (secs)" values with a trailing `?` (e.g. subject 32's `3500?`) are the plain numeric
  value; the `?` has no special meaning.
- "Eye Dominance" (100% missing in the amblyopia CSV) is not needed for any analysis.

## Columns excluded from any AI-assisted analysis

Per the data-handling rule in `CLAUDE.md`: `Referring Provider`, `Date of Testing`, `Notes` (both CSV and xlsx `Notes` sheet).
