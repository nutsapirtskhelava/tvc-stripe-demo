"""
tvc_stats.py

Statistical comparisons on the fitted IN (internal noise) and Psi (Weber
fraction) parameters from amblyopia_control_OD_OS_all_subjects-2.xlsx.

Reuses load_final_rows() / build_curve_groups() from plot_tvc_curves.py so the
subject exclusions (26, 32) and group definitions stay in one place.

Four comparisons, each run on both IN and Psi (8 tests total):
  1. Control OD      vs Fellow eye      -- independent groups (different people)
  2. Control OS      vs Amblyopic eye   -- independent groups
  3. Fellow eye       vs Amblyopic eye   -- paired (same amblyopic subjects, 2 eyes)
  4. Control OD      vs Control OS      -- paired (same control subjects, 2 eyes)

All tests run on log10(value) -- matches analyze_WF_internal_noise.m's convention,
appropriate since IN/Psi are right-skewed and bounded at zero. Each test is run
two ways:
  - parametric: Welch's t-test (independent) or paired t-test, on log10 values
  - nonparametric cross-check: Mann-Whitney U (independent) or Wilcoxon
    signed-rank (paired), as a check since the amblyopic-eye groups are only
    n=6 and t-test normality assumptions get shaky at that size.

Holm correction is applied within each parameter separately (2 families of 4
tests: one family for IN, one for Psi) -- matches the .m script's convention
of correcting within each parameter rather than across all 8 tests at once.

Before touching the real data, run_self_check() runs the same test function on
simulated data with a known planted effect, to confirm the code correctly
detects it -- a "does the pipeline work" check, separate from the real result.

Usage:
    python3 tvc_stats.py
Output:
    results/tvc_stats_table.csv
    printed table + plain-English summary per comparison
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

from plot_tvc_curves import load_final_rows, build_curve_groups, LOG_FLOOR

OUT_FILE = "results/tvc_stats_table.csv"
FIG_FILE = "results/Fig6_effect_sizes.png"
PARAMETERS = ["IN", "Psi"]
Z_95 = 1.96


def log10_floored(values):
    return np.log10(np.clip(np.asarray(values, dtype=float), LOG_FLOOR, None))


def cohens_d_independent(a, b):
    """Cohen's d on log10 values, pooled SD. Positive = a > b."""
    na, nb = len(a), len(b)
    pooled_sd = np.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    return (np.mean(a) - np.mean(b)) / pooled_sd


def cohens_dz_paired(diffs):
    """dz for paired design on log10 values: mean diff / SD of diffs."""
    return np.mean(diffs) / np.std(diffs, ddof=1)


def d_ci_independent(d, n1, n2):
    """Approximate 95% CI for Cohen's d (Hedges & Olkin, 1985 normal approximation)."""
    se = np.sqrt((n1 + n2) / (n1 * n2) + d ** 2 / (2 * (n1 + n2 - 2)))
    return d - Z_95 * se, d + Z_95 * se


def dz_ci_paired(dz, n):
    """Approximate 95% CI for paired dz, same normal-approximation family as d_ci_independent."""
    se = np.sqrt(1 / n + dz ** 2 / (2 * (n - 1)))
    return dz - Z_95 * se, dz + Z_95 * se


def holm_correct(pvals):
    """Holm step-down correction. Returns adjusted p-values, same order as input."""
    pvals = np.asarray(pvals, dtype=float)
    m = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    adjusted = np.empty(m)
    running_max = 0.0
    for i, p in enumerate(ranked):
        adj = min((m - i) * p, 1.0)
        running_max = max(running_max, adj)
        adjusted[i] = running_max
    out = np.empty(m)
    out[order] = adjusted
    return out


def independent_test(a, b, label_a, label_b, param):
    log_a, log_b = log10_floored(a), log10_floored(b)
    t_stat, t_p = stats.ttest_ind(log_a, log_b, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
    d = cohens_d_independent(log_a, log_b)
    ci_low, ci_high = d_ci_independent(d, len(a), len(b))
    return {
        "comparison": f"{label_a} vs {label_b}",
        "parameter": param,
        "design": "independent",
        "n1": len(a), "n2": len(b),
        "t_stat": t_stat, "t_p": t_p,
        "u_stat": u_stat, "u_p": u_p,
        "effect_size": d, "effect_label": "Cohen's d (log10 scale)",
        "ci_low": ci_low, "ci_high": ci_high,
    }


def paired_test(df_a, df_b, label_a, label_b, param):
    """df_a/df_b must each have a 'Subject' column; only matched subjects are kept."""
    merged = df_a[["Subject", param]].merge(
        df_b[["Subject", param]], on="Subject", suffixes=("_a", "_b")
    )
    dropped_a = set(df_a["Subject"]) - set(merged["Subject"])
    dropped_b = set(df_b["Subject"]) - set(merged["Subject"])
    if dropped_a or dropped_b:
        print(f"  [{label_a} vs {label_b}, {param}] unmatched subjects dropped: "
              f"only in {label_a}={sorted(dropped_a)}, only in {label_b}={sorted(dropped_b)}")

    log_a = log10_floored(merged[f"{param}_a"].values)
    log_b = log10_floored(merged[f"{param}_b"].values)
    t_stat, t_p = stats.ttest_rel(log_a, log_b)
    w_stat, w_p = stats.wilcoxon(merged[f"{param}_a"].values, merged[f"{param}_b"].values)
    dz = cohens_dz_paired(log_a - log_b)
    ci_low, ci_high = dz_ci_paired(dz, len(merged))
    return {
        "comparison": f"{label_a} vs {label_b}",
        "parameter": param,
        "design": "paired",
        "n1": len(merged), "n2": len(merged),
        "t_stat": t_stat, "t_p": t_p,
        "u_stat": w_stat, "u_p": w_p,
        "effect_size": dz, "effect_label": "Cohen's dz (log10 scale)",
        "ci_low": ci_low, "ci_high": ci_high,
    }


def run_self_check():
    """
    Sanity check on the test functions themselves, not the real data: plant a
    known effect in simulated log-normal data and confirm the independent and
    paired test functions both detect it. This does NOT touch the real xlsx.
    """
    rng = np.random.default_rng(0)
    n = 20
    # independent groups: group B shifted up by 0.3 log10 units (~2x) from group A
    a = 10 ** (rng.normal(np.log10(0.01), 0.15, n))
    b = 10 ** (rng.normal(np.log10(0.01) + 0.3, 0.15, n))
    result = independent_test(a, b, "SimA", "SimB", "sim_param")
    detected = result["t_p"] < 0.05 and result["u_p"] < 0.05
    print(f"Self-check (independent, planted ~2x shift): t_p={result['t_p']:.2e}, "
          f"u_p={result['u_p']:.2e}, d={result['effect_size']:.2f} -> "
          f"{'DETECTED as expected' if detected else 'NOT DETECTED -- investigate before trusting real results'}")

    # paired: same subjects, second measurement shifted up by 0.3 log10 units on
    # average, with a shared per-subject random effect (correlated pairs) plus
    # independent measurement noise -- NOT a deterministic shift, so the spread
    # of differences is realistic instead of collapsing to ~0
    subj = np.arange(1, n + 1)
    subject_effect = rng.normal(0, 0.1, n)
    before = 10 ** (np.log10(0.01) + subject_effect + rng.normal(0, 0.1, n))
    after = 10 ** (np.log10(0.01) + 0.3 + subject_effect + rng.normal(0, 0.1, n))
    df_a = pd.DataFrame({"Subject": subj, "sim_param": before})
    df_b = pd.DataFrame({"Subject": subj, "sim_param": after})
    result_p = paired_test(df_a, df_b, "SimBefore", "SimAfter", "sim_param")
    detected_p = result_p["t_p"] < 0.05 and result_p["u_p"] < 0.05
    print(f"Self-check (paired, planted ~2x shift): t_p={result_p['t_p']:.2e}, "
          f"w_p={result_p['u_p']:.2e}, dz={result_p['effect_size']:.2f} -> "
          f"{'DETECTED as expected' if detected_p else 'NOT DETECTED -- investigate before trusting real results'}")
    print()
    return detected and detected_p


def main():
    if not run_self_check():
        print("Self-check failed -- stopping before running on real data.")
        return

    final = load_final_rows()
    groups = build_curve_groups(final)

    comparisons = [
        ("independent", groups["Control OD"], groups["Fellow eye"], "Control OD", "Fellow eye"),
        ("independent", groups["Control OS"], groups["Amblyopic eye"], "Control OS", "Amblyopic eye"),
        ("paired", groups["Fellow eye"], groups["Amblyopic eye"], "Fellow eye", "Amblyopic eye"),
        ("paired", groups["Control OD"], groups["Control OS"], "Control OD", "Control OS"),
    ]

    rows = []
    for param in PARAMETERS:
        for design, g1, g2, l1, l2 in comparisons:
            if design == "independent":
                rows.append(independent_test(g1[param].values, g2[param].values, l1, l2, param))
            else:
                rows.append(paired_test(g1, g2, l1, l2, param))

    table = pd.DataFrame(rows)

    # Holm correction within each parameter separately (2 families of 4 tests)
    table["t_p_holm"] = np.nan
    table["u_p_holm"] = np.nan
    for param in PARAMETERS:
        mask = table["parameter"] == param
        table.loc[mask, "t_p_holm"] = holm_correct(table.loc[mask, "t_p"].values)
        table.loc[mask, "u_p_holm"] = holm_correct(table.loc[mask, "u_p"].values)

    table.to_csv(OUT_FILE, index=False)
    print(f"Saved results table to {OUT_FILE}\n")

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", None)
    print(table[["parameter", "comparison", "design", "n1", "n2", "t_p", "t_p_holm",
                 "u_p", "u_p_holm", "effect_size", "effect_label"]].to_string(index=False))

    print("\nPlain-English summary:")
    for _, r in table.iterrows():
        sig = "significant" if r["t_p_holm"] < 0.05 else "not significant"
        print(f"  [{r['parameter']}] {r['comparison']}: Holm-corrected t-test p={r['t_p_holm']:.4f} "
              f"({sig}), effect size={r['effect_size']:.2f}")

    plot_effect_sizes(table)
    print(f"\nSaved effect-size plot to {FIG_FILE}")


def plot_effect_sizes(table):
    """
    Forest-plot style figure: effect size (Cohen's d / dz) with 95% CI per
    comparison, one panel per parameter. Points whose CI crosses 0 are
    consistent with no effect; the Holm-corrected p-value from the table is
    the actual significance call, this is just a visual of effect magnitude.
    """
    fig, axes = plt.subplots(1, len(PARAMETERS), figsize=(11, 4), sharex=True)
    for ax, param in zip(axes, PARAMETERS):
        sub = table[table["parameter"] == param].reset_index(drop=True)
        y = np.arange(len(sub))
        ax.errorbar(
            sub["effect_size"], y,
            xerr=[sub["effect_size"] - sub["ci_low"], sub["ci_high"] - sub["effect_size"]],
            fmt="o", color="#1f77b4", capsize=4, linewidth=1.5, markersize=6,
        )
        ax.axvline(0, color="gray", linestyle="--", linewidth=1)
        ax.set_yticks(y)
        ax.set_yticklabels(sub["comparison"])
        ax.set_xlabel("Effect size (d / dz, log10 scale)")
        ax.set_title(param)
        ax.invert_yaxis()
        ax.grid(True, axis="x", alpha=0.3)

    fig.suptitle("Effect sizes with approx. 95% CI (Hedges normal approximation)")
    fig.tight_layout()
    fig.savefig(FIG_FILE, dpi=150)


if __name__ == "__main__":
    main()
