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

    TvC(c) = sqrt((IN^2 + c^2) * (1 + Psi)) - c

This is the exact dipper-function formula from the AIM-TvC+ method paper
(Skerswetat et al., Manuscript_TvC_R1.pdf, eq. 3) that this dataset's IN/Psi
columns were fit with -- confirmed by the matching column names (IN, Psi,
slopeEsts=sigma, minErrEsts=epsilon), chart structure, and tablet/ring
interface. It produces the real facilitation dip (minimum at c = IN/sqrt(Psi))
before the rising limb, unlike a naive sqrt(IN^2 + (Psi*c)^2) monotonic model.
Run analyze_WF_internal_noise.m if you want the statistical tests on IN/Psi
themselves -- this script only visualizes the resulting curve shape.

Group curves use the geometric mean (not arithmetic mean) of subject-level
IN/Psi, matching analyze_WF_internal_noise.m's log10-scale convention -- these
are right-skewed, zero-bounded parameters, so geometric mean is less distorted
by the handful of subjects pinned at the Psi=2.0 model ceiling.

Each panel also shows thin individual per-subject/eye curves (own fitted IN/Psi,
not the group mean) behind the bold group-mean curve, so you can see the
spread the mean is summarizing, not just the average.

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

# contrast range to evaluate the model over: matches the actual pedestal range
# used in the AIM-TvC+ task (0.001-0.9, log-spaced across 16 steps per the method paper)
CONTRAST_RANGE = np.logspace(np.log10(0.001), np.log10(0.9), 200)

OUT_DIR = "results"
OUT_FILE = f"{OUT_DIR}/Fig5_TvC_curves.png"


def tvc_threshold(contrast, internal_noise, weber_fraction):
    """AIM-TvC+ dipper function: TvC(c) = sqrt((IN^2 + c^2) * (1 + Psi)) - c."""
    return np.sqrt((internal_noise ** 2 + contrast ** 2) * (1 + weber_fraction)) - contrast


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

            # thin per-subject curves first (own IN/Psi, not the group mean), so the
            # bold group-mean line drawn after them sits on top and stays readable
            group_color = None
            for _, row in g.iterrows():
                subject_curve = tvc_threshold(CONTRAST_RANGE, row["IN"], row["Psi"])
                line, = ax.plot(CONTRAST_RANGE, subject_curve, linewidth=0.8, alpha=0.25,
                                 color=group_color, zorder=1)
                group_color = group_color or line.get_color()

            curve = tvc_threshold(CONTRAST_RANGE, mean_in, mean_psi)
            ax.plot(CONTRAST_RANGE, curve, label=f"{label} (n={n})", linewidth=2.5,
                     color=group_color, zorder=3)

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
    manual = ((mean_in ** 2 + check_contrast ** 2) * (1 + mean_psi)) ** 0.5 - check_contrast
    print(
        f"\nHand check -- {check_label} at contrast={check_contrast}: "
        f"sqrt(({mean_in:.4f}^2 + {check_contrast}^2) * (1 + {mean_psi:.4f})) - {check_contrast} = {manual:.4f}"
    )


if __name__ == "__main__":
    main()
