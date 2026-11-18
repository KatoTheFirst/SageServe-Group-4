"""Read-only structural checks of native SageServe LT-UA integration; no simulator run."""
from pathlib import Path
import argparse
import ast
import sys


def check(repo: Path) -> list[tuple[str, bool]]:
    arb = repo / 'arbiter.py'
    glob = repo / 'global_arbiter.py'
    runner = repo / 'experiments' / 'run.sh'
    for path in (arb, glob, runner):
        if not path.is_file():
            raise FileNotFoundError(path)
    src = arb.read_text(encoding='utf-8')
    tree = ast.parse(src)
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    cl = classes.get('GlobalArbiterARIMAChecking')
    methods = {n.name for n in cl.body if isinstance(n, ast.FunctionDef)} if cl else set()
    ass = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    try:
                        ass[tgt.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
    gl = glob.read_text(encoding='utf-8')
    sh = runner.read_text(encoding='utf-8')
    return [
        ('Native LT-UA class', cl is not None),
        ('LT-UA inherits memory scaling', bool(cl and any(isinstance(b, ast.Name) and b.id == 'GlobalAribiterMemoryUtilizationScaling' for b in cl.bases))),
        ('20-minute window in seconds', 'LTUA_WINDOW' in src and '20 * 60' in src),
        ('5x high-gap threshold', ass.get('LTUA_UP_RATIO') == 5.0),
        ('0.5x low-gap threshold', ass.get('LTUA_DOWN_RATIO') == 0.5),
        ('Forecast setter', 'set_arima_forecast' in methods),
        ('Gap-ratio method', 'ratio_between_arima_and_actual' in methods),
        ('LT-UA scale override', 'scale' in methods),
        ('Forecast propagated to local arbiters', 'set_arima_forecast' in gl),
        ('Runner has LT-U branch', 'global_arbiter_memory_utilization' in sh),
        ('Runner has LT-UA branch', 'global_arbiter_ARIMA_checking' in sh),
        ('Runner uses v2 main trace', 'composed_day_3regions_v2' in sh),
        ('Runner uses theta-v2', 'theta_tps_v2.csv' in sh),
    ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', nargs='?', default='.')
    args = parser.parse_args()
    try:
        findings = check(Path(args.repo))
    except Exception as exc:
        print(f'ERROR: {exc}')
        sys.exit(2)
    for title, ok in findings:
        print(f"{'PASS' if ok else 'FAIL'}: {title}")
    print(f'{sum(x[1] for x in findings)}/{len(findings)} read-only structural checks passed')
    sys.exit(0 if all(x[1] for x in findings) else 1)
