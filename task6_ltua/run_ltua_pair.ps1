# Chay LT-U va LT-UA TUAN TU tren cung trace v2, khong sua ma nguon.
param(
    [string]$Repo = (Get-Location).Path,
    [int]$EndTime = 86400,
    [string]$ResultsRoot = "results/task6_v21"
)
$ErrorActionPreference = 'Stop'
Set-Location $Repo
$env:PYTHONIOENCODING = 'utf-8'
$Python = Join-Path $Repo '.venv/Scripts/python.exe'
if (-not (Test-Path $Python)) { throw "Khong tim thay $Python. Hay tao .venv Python 3.11 va cai requirements.txt." }
$required = @('run.py','arbiter.py','global_arbiter.py','data/theta_tps_v2.csv', 'traces/composed_day_3regions_v2.csv', 'traces/forecasts/composed_day_3regions_v2')
foreach ($p in $required) { if (-not (Test-Path $p)) { throw "Thieu: $p. Xem REPRODUCE.md ve trace-v2." } }
$common = @(
  'trace=random_trace',
  'trace.filename=composed_day_3regions_v2',
  'controller=us3-4models',
  'performance_model.db_path=data/perf_model_4models.csv',
  'global_arbiter.arima_traces=traces/forecasts/composed_day_3regions_v2',
  'global_arbiter.theta_file=data/theta_tps_v2.csv',
  'long_term_scaling=True',
  "end_time=$EndTime"
)
New-Item -ItemType Directory -Force -Path $ResultsRoot | Out-Null
foreach ($name in @('lt_u','lt_ua')) {
  $policy = if ($name -eq 'lt_u') {'global_arbiter_memory_utilization'} else {'global_arbiter_ARIMA_checking'}
  $args = @('run.py') + $common + @(
    "controller.regions.0.arbiter=$policy",
    "controller.regions.1.arbiter=$policy",
    "controller.regions.2.arbiter=$policy",
    "output_dir=$ResultsRoot/$name"
  )
  Write-Host "Running $name with trace-v2, $EndTime seconds..."
  & $Python @args
  if ($LASTEXITCODE -ne 0) { throw "$name that bai (exit $LASTEXITCODE)" }
}
& $Python 'analyze_s4.py' "$ResultsRoot/lt_u" "$ResultsRoot/lt_ua" '--skip_hours' '1' '--out' "$ResultsRoot/analysis"
if ($LASTEXITCODE -ne 0) { throw 'Phan tich that bai' }
Write-Host "Hoan thanh. Kiem tra $ResultsRoot/analysis"
