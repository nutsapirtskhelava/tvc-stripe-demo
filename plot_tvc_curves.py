"""
plot_tvc_curves.py

Plots theoretical threshold-vs-contrast (TvC) curves from the fitted
internal-noise (IN) and Weber-fraction (Psi) parameters in
amblyopia_control_OD_OS_all_subjects-2.xlsx, sheet 'AllData'.

WHY A "THEORETICAL" CURVE: the xlsx only has, per subject/eye, a single fitted
IN and Psi (from the "Final" row of the adaptive procedure) -- not raw
trial-by-trial pedestal-contrast/response data. So instead of plotting
measured thresholds at each tested contrast, this script plots what the
fitted noise model predicts the threshold would be across a range of
contrasts:

    threshold(c) = sqrt(IN^2 + (Psi * c)^2)

This is the standard additive-plus-multiplicative noise model: IN sets the
threshold floor at low contrast (c -> 0), and Psi sets the slope at high
contrast. Run analyze_WF_internal_noise.m first if you want the statistical
tests on IN/Psi themselves -- this script only visualizes the resulting curve
shape.

Group curves use the geometric mean (not arithmetic mean) of subject-level
IN/Psi, matching analyze_WF_internal_noise.m's log10-scale convention -- these
are right-skewed, zero-bounded parameters, so geometric mean is less distorted
by the handful of subjects pinned at the Psi=2.0 model ceiling.

Usage:
    python3 plot_tvc_curves.py
Output:
    results/Fig5_TvC_curves.png
    prints the group geometric-mean IN/Psi feeding each curve, and a hand-check value
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DATA_FILE = "amblyopia_control_OD_OS_all_subjects-2.xlsx"
SHEET = "AllData"
FINAL_CHART_NUM = 6  # the "Final" row per subject/eye holds the overall fitted IN/Psi

# excluded per user instruction: 26 did not understand the task; 32 has no TvC data
EXCLUDE_SUBJECTS = [26, 32]

# IN/Psi are noise/threshold-type parameters: right-skewed, bounded at zero, so
# geometric mean (matches the .m script's log10-scale convention) is used instead
# of arithmetic mean -- it's also less distorted by the Psi=2.0 ceiling-pinned values.
LOG_FLOOR = 1e-4  # replaces 0 before log, in case a Final value is ever exactly 0

# contrast range to evaluate the model over (log-spaced, matches typical pedestal range)
CONTRAST_RANGE = np.logspace(np.log10(0.005), np.log10(1.0), 200)

OUT_DIR = "results"
OUT_FILE = f"{OUT_DIR}/Fig5_TvC_curves.png"


def tvc_threshold(contrast, internal_noise, weber_fraction):
    """Additive + multiplicative noise model: threshold(c) = sqrt(IN^2 + (Psi*c)^2)."""
    return np.sqrt(internal_noise ** 2 + (weber_fraction * contrast) ** 2)


def geometric_mean(values):
    """exp(mean(log(x))), flooring zeros first -- see LOG_FLOOR note above."""
    floored = np.clip(values, LOG_FLOOR, None)
    return float(np.exp(np.mean(np.log(floored))))


def load_final_rows():
    df = pd.read_excel(DATA_FILE, sheet_name=SHEET)
    df = df[~df["Subject"].isin(EXCLUDE_SUBJECTS)]
    final = df[df["ChartNum"] == FINAL_CHART_NUM].copy()
    return final


def build_curve_groups(final):
    """
    Returns a dict: group label -> (subject-level IN array, Psi array)
    Groups follow the comparisons mentioned for this study:
      - Control OD vs Control OS
      - Amblyopic eye vs Fellow eye (within amblyopes)
      - Amblyopes (both eyes pooled) vs Controls (both eyes pooled)
    EyeStatus column already encodes Control / Fellow / Amblyopic per row.
    """
    groups = {}
    control = final[final["EyeStatus"] == "Control"]
    groups["Control OD"] = control[control["Eye"] == "OD"]
    groups["Control OS"] = control[control["Eye"] == "OS"]

    groups["Amblyopic eye"] = final[final["EyeStatus"] == "Amblyopic"]
    groups["Fellow eye"] = final[final["EyeStatus"] == "Fellow"]

    groups["All Controls (OD+OS)"] = control
    groups["All Amblyopes (AE+FE)"] = final[final["EyeStatus"].isin(["Amblyopic", "Fellow"])]

    return groups


def main():
    final = load_final_rows()
    groups = build_curve_groups(final)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    panels = [
        ("Control OD vs OS", ["Control OD", "Control OS"], axes[0]),
        ("Amblyopic vs Fellow eye", ["Amblyopic eye", "Fellow eye"], axes[1]),
        ("Amblyopes vs Controls", ["All Amblyopes (AE+FE)", "All Controls (OD+OS)"], axes[2]),
    ]

    print("Group geometric-mean fitted parameters feeding each curve (n = number of eyes):")
    for title, labels, ax in panels:
        for label in labels:
            g = groups[label]
            n = len(g)
            if n == 0:
                print(f"  {label}: no data, skipping")
                continue
            mean_in = geometric_mean(g["IN"].values)
            mean_psi = geometric_mean(g["Psi"].values)
            print(f"  {label}: n={n}, geomean IN={mean_in:.4f}, geomean Psi={mean_psi:.4f}")

            curve = tvc_threshold(CONTRAST_RANGE, mean_in, mean_psi)
            ax.plot(CONTRAST_RANGE, curve, label=f"{label} (n={n})", linewidth=2)

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Pedestal contrast")
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.3)

    axes[0].set_ylabel("Predicted orientation discrimination threshold")
    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=150)
    print(f"\nSaved figure to {OUT_FILE}")

    # hand-verification: pick one group/contrast and show the arithmetic explicitly
    check_label = "Control OD"
    check_contrast = 0.1
    g = groups[check_label]
    mean_in = geometric_mean(g["IN"].values)
    mean_psi = geometric_mean(g["Psi"].values)
    manual = (mean_in ** 2 + (mean_psi * check_contrast) ** 2) ** 0.5
    print(
        f"\nHand check -- {check_label} at contrast={check_contrast}: "
        f"sqrt({mean_in:.4f}^2 + ({mean_psi:.4f} * {check_contrast})^2) = {manual:.4f}"
    )


if __name__ == "__main__":
    main()
