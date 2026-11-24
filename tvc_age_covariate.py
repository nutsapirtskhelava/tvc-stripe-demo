"""
tvc_age_covariate.py

Checks whether Age matters for the Group x Eye comparisons that
analyze_WF_internal_noise.m and tvc_stats.py both run on IN and Psi.

WHY: this is a developmental sample (ages 6-17), and neither the .m script
nor tvc_stats.py reads the demographics CSVs -- age plays no role in either.
Age is NOT a confound for the group comparison itself (amblyopia vs control
age distributions are not significantly different, see notes/data-map.md),
but Psi (Weber fraction) shows an age trend worth controlling for, since
contrast gain control is known to keep maturing through childhood.

Two linear mixed models are fit per parameter (log10 scale, Subject as
random intercept, matching analyze_WF_internal_noise.m's convention):
    1. log10(param) ~ Group * Eye                (no age; same as the .m script)
    2. log10(param) ~ Group * Eye + Age           (age as an additive covariate)
Comparing (1) and (2) shows whether adding age changes the Group/Eye effect's
size or significance -- NOT a three-way Group*Eye*Age interaction, which
17 subjects (6 amblyopic) cannot support without overfitting.

Usage:
    python3 tvc_age_covariate.py
Output:
    prints both models' fixed-effect tables for IN and Psi
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from plot_tvc_curves import load_final_rows, LOG_FLOOR

AGE_FILES = [
    "AIM TvC Subjects Deidentified (Amblyopia).csv",
    "AIM TvC Subjects Deidentified (Control 2).csv",
]


def load_ages():
    frames = [pd.read_csv(f)[["SUBJECT ID", "Age"]] for f in AGE_FILES]
    ages = pd.concat(frames).rename(columns={"SUBJECT ID": "Subject"})
    return ages


def build_model_frame():
    final = load_final_rows()
    ages = load_ages()
    df = final.merge(ages, on="Subject")
    df["Eye2"] = df["Eye"].map({"OD": "RightOrFellow", "OS": "LeftOrAmblyopic"})
    # EyeStatus already encodes Fellow/Amblyopic for the amblyopia group, so the
    # physical-eye recode above matches analyze_WF_internal_noise.m's "PI" convention
    # (fellow eye grouped with control OD, amblyopic eye grouped with control OS)
    df.loc[df["EyeStatus"] == "Fellow", "Eye2"] = "RightOrFellow"
    df.loc[df["EyeStatus"] == "Amblyopic", "Eye2"] = "LeftOrAmblyopic"
    for param in ["IN", "Psi"]:
        df[f"log10_{param}"] = np.log10(np.clip(df[param].values, LOG_FLOOR, None))
    return df


def fit_and_report(df, param, with_age):
    formula = f"log10_{param} ~ Group * Eye2" + (" + Age" if with_age else "")
    model = smf.mixedlm(formula, df, groups=df["Subject"])
    result = model.fit(reml=False)
    label = "WITH age covariate" if with_age else "WITHOUT age (matches .m script)"
    print(f"\n--- {param}: {label} ---")
    print(result.summary().tables[1])
    return result


def main():
    df = build_model_frame()
    print(f"n subjects = {df['Subject'].nunique()}, n eye-observations = {len(df)}")
    print(f"Age range: {df['Age'].min()}-{df['Age'].max()}, mean={df['Age'].mean():.1f}")

    for param in ["IN", "Psi"]:
        fit_and_report(df, param, with_age=False)
        fit_and_report(df, param, with_age=True)


if __name__ == "__main__":
    main()
