"""So hai bài mô phỏng theo số liệu (kiểm tái lập): summary/*.csv và detailed/<instance>/*.csv.
Bỏ qua log, .hydra, thời gian, đường dẫn. Số thực lệch ≤ TOL.
1) So từng dòng. Khóa sắp xếp lấy từ trace: detailed = (prompt_sizes, token_sizes) – model/vùng đã nằm ở tên thư mục instance,
   file không có thời điểm đến hay tier; summary = application_id. Khi khóa trace trùng nhau, các cột còn lại làm khóa phụ.
2) Nếu từng dòng khác: so tổng hợp theo file (số dòng, tổng chính xác bằng math.fsum, P50/P95/P99 của cột độ trễ)
   và instance-hours theo mô hình của cả bài. Tổng hợp trùng -> "khác do căn dòng, số liệu trùng" (coi như trùng).
Dùng: python experiments/compare_runs.py <bài A> <bài B> [--tol 1e-9]. Mã thoát 0 = trùng, 1 = không tất định."""
import argparse
import glob
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from analyze_s4 import analyze

TRACE_KEYS = {"detailed": ["prompt_sizes", "token_sizes"], "summary": ["application_id"]}
LATENCY = ["response_times", "queue_times", "ttft_times", "tbt_times", "nth_token_overheads"]


def files(run):
    pats = ("summary/*.csv", "detailed/*/*.csv")
    return sorted(os.path.relpath(f, run).replace("\\", "/") for p in pats for f in glob.glob(f"{run}/{p}"))


def sort_rows(df, kind):
    keys = [k for k in TRACE_KEYS[kind] if k in df]
    if df.duplicated(keys).any():                 # khóa trace không đủ phân biệt -> thêm cột khác làm khóa phụ
        keys += [c for c in df.columns if c not in keys]
    return df.sort_values(keys, ignore_index=True, na_position="first")


def row_diffs(x, y, f, tol):
    out = []
    for c in x.columns:
        if pd.api.types.is_numeric_dtype(x[c]) and pd.api.types.is_numeric_dtype(y[c]):
            u, v = x[c].to_numpy(float), y[c].to_numpy(float)
            bad = ~((np.abs(u - v) <= tol) | (np.isnan(u) & np.isnan(v)))
            if bad.any():
                out.append(f"{f} cột {c}: {bad.sum()} dòng lệch, lệch lớn nhất {np.nanmax(np.abs(u - v)):.3g}")
        elif not x[c].equals(y[c]):
            out.append(f"{f} cột {c}: {(x[c] != y[c]).sum()} giá trị khác")
    return out


def aggregate(df):
    """Thống kê không phụ thuộc thứ tự dòng."""
    s = {"rows": float(len(df))}
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            v = df[c].dropna().to_numpy(float)
            s[f"{c}:sum"] = math.fsum(v)          # tổng làm tròn đúng, không phụ thuộc thứ tự
            if any(c.startswith(l) for l in LATENCY):
                for q in (50, 95, 99):
                    s[f"{c}:p{q}"] = float(np.percentile(v, q)) if len(v) else math.nan
    return s


def agg_diffs(sa, sb, f, tol):
    out = []
    for k in sorted(set(sa) | set(sb)):
        u, v = sa.get(k, math.nan), sb.get(k, math.nan)
        if not (abs(u - v) <= tol or (math.isnan(u) and math.isnan(v))):
            out.append(f"{f} {k}: {u!r} và {v!r} (lệch {abs(u - v):.3g})")
    return out


def compare(a, b, tol):
    """Trả về (khác từng dòng, khác tổng hợp, số file chung)."""
    rows, aggs = [], []
    fa, fb = files(a), files(b)
    for f in sorted(set(fa) ^ set(fb)):
        rows.append(f"{f}: chỉ có ở {'A' if f in fa else 'B'}")
        aggs.append(rows[-1])
    for f in sorted(set(fa) & set(fb)):
        x, y = pd.read_csv(f"{a}/{f}"), pd.read_csv(f"{b}/{f}")
        if list(x.columns) != list(y.columns):
            rows.append(f"{f}: cột khác")
            aggs.append(rows[-1])
            continue
        kind = f.split("/")[0]
        r = [f"{f}: số dòng {len(x)} và {len(y)}"] if len(x) != len(y) else row_diffs(sort_rows(x, kind), sort_rows(y, kind), f, tol)
        if r:
            rows += r
            aggs += agg_diffs(aggregate(x), aggregate(y), f, tol)
    if rows and os.path.isdir(f"{a}/memory") and os.path.isdir(f"{b}/memory"):   # instance-hours theo mô hình của cả bài
        ia, ib = analyze(a, 1)[0].instance_hours, analyze(b, 1)[0].instance_hours
        aggs += agg_diffs({f"IH {m}": float(v) for m, v in ia.items()}, {f"IH {m}": float(v) for m, v in ib.items()}, "bài", tol)
    return rows, aggs, len(set(fa) & set(fb))


def overrides(run):
    """Khóa=giá trị trong .hydra/overrides.yaml (bỏ output_dir) và biến SAGE_* trong sage_env.txt (run.py ghi lúc chạy);
    None nếu thiếu một trong hai file – bài chạy trước khi có sage_env.txt không đối chiếu được."""
    p, e = f"{run}/.hydra/overrides.yaml", f"{run}/sage_env.txt"
    if not (os.path.exists(p) and os.path.exists(e)):
        return None
    items = [l.strip()[2:] for l in open(p, encoding="utf-8") if l.strip().startswith("- ")]
    items += [l.strip() for l in open(e, encoding="utf-8") if l.strip()]
    return {k: v for k, _, v in (i.partition("=") for i in items) if k != "output_dir"}


def config_diff(a, b):
    ca, cb = overrides(a), overrides(b)
    if ca is None or cb is None:
        return None
    return sorted(k for k in set(ca) | set(cb) if ca.get(k) != cb.get(k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--tol", type=float, default=1e-9)
    a = ap.parse_args()
    rows, aggs, n = compare(a.a, a.b, a.tol)
    keys = config_diff(a.a, a.b)
    print(f"{n} file chung; so từng dòng: {len(rows)} khác biệt; cấu hình khác ở: "
          f"{'không đọc được .hydra/overrides.yaml hoặc sage_env.txt' if keys is None else (keys or 'không')}")
    for d in rows[:20]:
        print("  ", d)
    if rows:
        print(f"so tổng hợp: {len(aggs)} khác biệt")
        for d in aggs[:30]:
            print("  ", d)
    if not rows:
        print("KẾT LUẬN: TRÙNG")
    elif not aggs:
        print("KẾT LUẬN: TRÙNG, khác do căn dòng")
    elif keys is None:
        print("KẾT LUẬN: KHÁC (không đối chiếu được cấu hình)")
    elif keys:
        print(f"KẾT LUẬN: KHÁC (cấu hình khác: {', '.join(keys)})")
    else:
        print("KẾT LUẬN: KHÔNG TẤT ĐỊNH")
    sys.exit(0 if not aggs else 1)


if __name__ == "__main__":
    main()
