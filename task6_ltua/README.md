# Task 6 — LT-UA (SageServe Group 4, trace v2 / results v2.1)

## Status

The group's current repo already includes `GlobalArbiterARIMAChecking` in `arbiter.py` and LT-UA wiring in `global_arbiter.py`. **Do not use legacy `patch_arbiter.py` to overwrite it.** This package is a documentation, verification, and reproduction supplement; it does not replace native simulator code.

## Required runtime

- Windows PowerShell; Python 3.11 virtual environment `.venv` in the repository root.
- Install `requirements.txt` from the current repo.
- Main trace **v2** `traces/composed_day_3regions_v2.csv`, forecast directory `traces/forecasts/composed_day_3regions_v2`, `data/theta_tps_v2.csv` (see `REPRODUCE.md`; `fetch_traces.py` only fetches v1).

## Commands

From repo root:

```powershell
.\.venv\Scripts\python.exe path\to\verify_native_ltua.py .
& 'path\to\run_ltua_pair.ps1' -Repo (Get-Location).Path -EndTime 86400
```

The run script executes LT-U then LT-UA sequentially on the same v2 trace and hardware/controller/forecast configuration. It invokes `analyze_s4.py` with `--skip_hours 1`. For a smoke test use `-EndTime 7200`, but **do not confuse smoke-test metrics with the published full-day results**.

## Evidence classification

- `RESULTS.md` published group outcomes (as of 2026-11-18). The published outcomes were not independently rerun here.
- `verify_native_ltua.py` performs structural source checks only, **not** functional or end-to-end tests.
- An actual experiment requires the current repo, trace files, local setup, and sufficient compute/storage; compare output with `RESULTS.md` and `sage_env.txt` commit/version.

## Source references

- https://github.com/KatoTheFirst/SageServe-Group-4/blob/main/arbiter.py
- https://github.com/KatoTheFirst/SageServe-Group-4/blob/main/global_arbiter.py
- https://github.com/KatoTheFirst/SageServe-Group-4/blob/main/RESULTS.md
- https://github.com/KatoTheFirst/SageServe-Group-4/blob/main/REPRODUCE.md
- https://github.com/KatoTheFirst/SageServe-Group-4/blob/main/experiments/run.sh
