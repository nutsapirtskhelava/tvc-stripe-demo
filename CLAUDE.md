# Project notes

## AIM TvC Study — contrast discrimination in amblyopia

Data: de-identified subject files in this folder (amblyopia CSV, control CSV, combined OD/OS xlsx).
Task: click/tap the direction of oriented stripes in rings, 4x4 grid (16 rings) per chart, 5 charts
per eye, contrast is adaptive (staircase). One eye patched while the other is tested, then switch.

### Data handling rule
Do NOT read, print, or analyze these columns from the subject CSVs/xlsx:
- "Referring Provider"
- "Date of Testing"
- "Notes"

These were excluded per the user's decision on 2026-11-24 pending full IRB/BU-guidance confirmation
for AI-assisted analysis of those specific fields. All other de-identified columns (subject ID,
age, sex, diagnosis, VA, stereoacuity, etc.) are approved for inspection/analysis in this session.

### Git rule
Raw subject-level files (the two CSVs and the combined xlsx) are excluded from git via
`.gitignore` and must never be pushed to GitHub, even de-identified.
